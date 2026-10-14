"""Value board: rank everything seen recently by measured perf/€, perf/W, raw marks.

No network: CPU extraction (exact + family-seed estimates) + cached benchmarks
+ kind classification only. Unrated items are counted split by kind so
non-systems (clothes, bags, accessories) never inflate the "missing gems" number.
"""
from __future__ import annotations

import time


def cached_cpu(cpu: str) -> dict | None:
    """PassMark entry from disk/memory cache only (None when never fetched)."""
    from .benchmarks import cached_cpu as _cc
    return _cc(cpu)


def _board_word(blob: str) -> bool:
    """Raw board-word presence (motherboard/mainboard/carte mère/...)."""
    try:
        from .scoring import board_info as _bi
        return bool(_bi(blob)[0])
    except Exception:
        return False


def _board_fields(blob: str, price: float | None, multi: int) -> dict:
    """Board leaderboard math: soldered boards rank by effective complete cost
    (price + typical completion minus already-included RAM/SSD); socket
    platforms carry no completion math."""
    from .scoring import BOARD_COMPLETION_EUR, board_info
    from .scoring import extract_ram as _r
    from .scoring import extract_storage as _s
    try:
        is_board, socketed = board_info(blob)
    except Exception:
        return {"board": False, "socketed": False, "eff_price": 0, "eff_ppe": 0}
    if not is_board:
        return {"board": False, "socketed": False, "eff_price": 0, "eff_ppe": 0}
    completion = 0 if socketed else BOARD_COMPLETION_EUR
    if completion:
        try:
            if _r(blob) is not None:
                completion -= 35
            gb, _ = _s(blob)
            if gb:
                completion -= 40
        except Exception:
            pass
        completion = max(40, completion)
    eff = (price or 0) + completion if price else 0
    return {"board": True, "socketed": socketed, "eff_price": eff,
            "eff_ppe": round(multi / eff, 1) if eff else 0}


def collect_full(store, days: float = 14.0,
                 fav_ids: set[str] | None = None) -> tuple[list[dict], dict]:
    """All recently-seen listings + favorites, enriched from cache.

    Returns (items, counts) with counts = {rated, estimated, unrated_systems,
    unrated_nonsystem}. Estimated items carry the seed base CPU (labeled) so
    they rank approximately instead of vanishing into "unrated".
    """
    from .decision import heuristic_decide
    from .scoring import extract_ram as _ram
    from .scoring import extract_storage as _stor
    from .scoring import is_barebone, resolve_cpu_with_seeds, to_eur
    cutoff = time.time() - days * 86400
    try:
        rows = store.db.execute(
            "SELECT id, title, price, currency, url, source, data FROM listings "
            "WHERE last_seen >= ? ORDER BY last_seen DESC LIMIT 20000", (cutoff,)).fetchall()
    except Exception:
        return [], {"rated": 0, "estimated": 0,
                    "unrated_systems": 0, "unrated_nonsystem": 0}
    favs = fav_ids if fav_ids is not None else set()
    items: list[dict] = []
    counts = {"rated": 0, "estimated": 0,
              "unrated_systems": 0, "unrated_nonsystem": 0}
    for lid, title, price, cur, url, src, data in rows:
        title = title or ""
        try:
            import json as _j
            blob = _j.loads(data or "{}")
            desc = blob.get("description", "") or ""
            imgs = blob.get("images", []) or []
        except Exception:
            desc, imgs = "", []
        try:
            kind = heuristic_decide(title, desc, price, "").get("kind", "offer")
        except Exception:
            kind = "offer"
        cpu, _, _, estimated, _ = resolve_cpu_with_seeds(f"{title}\n{desc}")
        try:
            from .scoring import board_info as _bi
            _is_b, _sock = _bi(f"{title}\n{desc}")
        except Exception:
            _is_b, _sock = False, False
        bench = cached_cpu(cpu) if cpu else None
        multi = (bench or {}).get("multi")
        if not multi:
            if kind == "offer":
                counts["unrated_systems"] += 1
            else:
                counts["unrated_nonsystem"] += 1
            if _is_b and kind == "offer":
                # recognized but unratable (bare socket platform, ARM SBC,
                # exotic chip): visible in the platforms list, never in perf/€.
                items.append({"id": lid, "title": title[:100], "price": price,
                              "currency": cur or "EUR", "url": url, "source": src,
                              "image": imgs[0] if imgs else "", "cpu": cpu,
                              "multi": None, "single": None, "tdp_w": None,
                              "kind": kind, "fav": lid in favs,
                              "estimated": estimated, "board": True,
                              "socketed": _sock, "platform_only": True,
                              "ppe": 0, "ppe_full": 0, "ppw": 0,
                              "barebone_uplift": 0, "full_price": price or 0,
                              "eff_price": price or 0, "eff_ppe": 0})
            continue
        if estimated:
            counts["estimated"] += 1
        else:
            counts["rated"] += 1
        # complete-system cost: barebone units need RAM (~85/16GB) and a drive
        # (~40/512GB) added before perf/€ means anything. Bare CPUs (tray chips
        # like "E5-2667 v4 SR2LF") and chip-only listings with no system context
        # ("Ryzen 5 5600x" alone) need board+RAM on top (~150). Raw ppe kept too.
        uplift = 0
        try:
            import re as _reU
            blob = f"{title}\n{desc}"
            if is_barebone(blob):
                if _ram(blob) is None:
                    uplift += 85
                gb, _ = _stor(blob)
                if not gb:
                    uplift += 40
            elif cpu and _ram(blob) is None and not _board_word(blob):
                if _reU.search(r"\btray\b|\bboxed\b|\bsr[0-9a-z]{3}\b|\bcpu\b|\bprozessor\b|"
                               r"\bprocessor\b|\bchip\b|\bpuce\b|\bprocesseur\b|\bprocessore\b|"
                               r"\bprocesador\b", blob, _reU.IGNORECASE) or not _reU.search(
                               r"laptop|notebook|mini\s*pc|desktop|\bpc\b|thinkpad|elitebook|"
                               r"macbook|server|workstation|imac|\bnuc\b|tablet|phone|console",
                               blob, _reU.IGNORECASE):
                    uplift += 150
        except Exception:
            uplift = 0
        # All-in cost: item + SHIPPING. Round 21 proved cards without shipping
        # rank China/US listings as cheapest while $100/$567 freight makes them
        # the most expensive. shipping_cost lives on the listing blob (drivers
        # must wire it — ebay-web does since round 22).
        ship = 0.0
        try:
            import json as _j2
            _blob2 = _j2.loads(data or "{}")
            _sc = _blob2.get("shipping_cost")
            if _sc is None:
                _sc = (_blob2.get("attributes") or {}).get("shipping")
            ship = float(_sc or 0.0)
        except (TypeError, ValueError):
            ship = 0.0
        full_price = (price or 0) + uplift + ship if price else 0
        try:
            pe = to_eur(price, cur or "EUR") or 0
        except Exception:
            pe = price or 0
        full_eur = pe + uplift + ship if pe else 0
        single = (bench or {}).get("single")
        tdp = None
        try:
            tdp = float(str((bench or {}).get("tdp") or "").split()[0])
        except (TypeError, ValueError, IndexError):
            tdp = None
        items.append({"id": lid, "title": title[:100], "price": price,
                      "currency": cur or "EUR", "url": url, "source": src,
                      "image": imgs[0] if imgs else "",
                      "cpu": cpu, "multi": multi, "single": single, "tdp_w": tdp,
                      "kind": kind, "fav": lid in favs,
                      "estimated": estimated,
                      # Same rule as the search pipeline (orchestrator): bench
                      # per euro > 400 is almost never the system itself —
                      # cooler, charger, empty box. Review material, not a gem.
                      "implausible": bool(pe and multi and multi / pe > 400),
                      "barebone_uplift": uplift, "ship": round(ship, 2),
                      "full_price": full_price,
                      "ppe": round(multi / pe, 1) if pe else 0,
                      "ppe_full": round(multi / full_eur, 1) if full_eur else 0,
                      "ppw": round(multi / tdp, 1) if tdp else 0,
                      **_board_fields(f"{title}\n{desc}", pe, multi)})
    return items, counts


def collect(store, days: float = 14.0, fav_ids: set[str] | None = None) -> tuple[list[dict], int]:
    """Backward-compatible wrapper: unrated = systems-only unrated (offers)."""
    items, counts = collect_full(store, days=days, fav_ids=fav_ids)
    return items, counts["unrated_systems"]


def _has_own_cpu(x: dict) -> bool:
    """Socketed listing naming its own CPU (desktop combo) is a system, not a
    bare platform."""
    try:
        from .scoring import extract_cpu
        cpu, _, _ = extract_cpu(x.get("title") or "")
        return bool(cpu)
    except Exception:
        return False


def board(items: list[dict], min_bench: int = 8000, max_risk: float | None = None,
          systems_only: bool = True, limit: int = 30) -> dict:
    """Three ranked lists. Systems-only drops accessory/parts/want kinds.
    The perf/€ list ranks by complete-system cost (barebone uplift included);
    raw ppe stays on each row for transparency."""
    pool = [x for x in items if (x["multi"] or 0) >= min_bench]
    if systems_only:
        pool = [x for x in pool if x.get("kind", "offer") == "offer"]
    if max_risk is not None:
        pool = [x for x in pool if (x.get("risk") or 0) <= max_risk]

    def _rank(xs: list[dict], key) -> list[dict]:
        """Rank by key; implausible (bench/€ > 400) sorts last, never hidden —
        same review-lane philosophy as the search pipeline."""
        return sorted(xs, key=lambda z: (bool(z.get("implausible")), key(z)))[:limit]

    eff = [x for x in pool if (x.get("ppw") or 0) >= 700]
    boards = _rank([x for x in items if x.get("board") and not x.get("socketed")
                    and not x.get("platform_only")
                    and x.get("kind", "offer") == "offer"
                    and (x["multi"] or 0) >= min_bench],
                   lambda z: -z["eff_ppe"])
    platforms = sorted((x for x in items if x.get("board")
                        and x.get("kind", "offer") == "offer"
                        and (x.get("socketed") or x.get("platform_only"))
                        and not (x.get("multi") and _has_own_cpu(x))),
                       key=lambda z: (z.get("price") is None, z.get("price") or 0))[:limit]
    return {"ppe": _rank(pool, lambda z: -(z.get("ppe_full") or z["ppe"])),
            "efficient": _rank(eff, lambda z: -z["ppe"]),
            "ppw": _rank([x for x in pool if x.get("ppw")], lambda z: -z["ppw"]),
            "raw": _rank(pool, lambda z: -(z["multi"] or 0)),
            "boards": boards, "platforms": platforms,
            "n": len(pool)}

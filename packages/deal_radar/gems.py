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


def collect_full(store, days: float = 14.0,
                 fav_ids: set[str] | None = None) -> tuple[list[dict], dict]:
    """All recently-seen listings + favorites, enriched from cache.

    Returns (items, counts) with counts = {rated, estimated, unrated_systems,
    unrated_nonsystem}. Estimated items carry the seed base CPU (labeled) so
    they rank approximately instead of vanishing into "unrated".
    """
    from .decision import heuristic_decide
    from .scoring import resolve_cpu_with_seeds
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
        bench = cached_cpu(cpu) if cpu else None
        multi = (bench or {}).get("multi")
        if not multi:
            if kind == "offer":
                counts["unrated_systems"] += 1
            else:
                counts["unrated_nonsystem"] += 1
            continue
        if estimated:
            counts["estimated"] += 1
        else:
            counts["rated"] += 1
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
                      "ppe": round(multi / price, 1) if price else 0,
                      "ppw": round(multi / tdp, 1) if tdp else 0})
    return items, counts


def collect(store, days: float = 14.0, fav_ids: set[str] | None = None) -> tuple[list[dict], int]:
    """Backward-compatible wrapper: unrated = systems-only unrated (offers)."""
    items, counts = collect_full(store, days=days, fav_ids=fav_ids)
    return items, counts["unrated_systems"]


def board(items: list[dict], min_bench: int = 8000, max_risk: float | None = None,
          systems_only: bool = True, limit: int = 30) -> dict:
    """Three ranked lists. Systems-only drops accessory/parts/want kinds."""
    pool = [x for x in items if (x["multi"] or 0) >= min_bench]
    if systems_only:
        pool = [x for x in pool if x.get("kind", "offer") == "offer"]
    if max_risk is not None:
        pool = [x for x in pool if (x.get("risk") or 0) <= max_risk]
    eff = [x for x in pool if (x.get("ppw") or 0) >= 700]
    return {"ppe": sorted(pool, key=lambda z: -z["ppe"])[:limit],
            "efficient": sorted(eff, key=lambda z: -z["ppe"])[:limit],
            "ppw": sorted([x for x in pool if x.get("ppw")], key=lambda z: -z["ppw"])[:limit],
            "raw": sorted(pool, key=lambda z: -(z["multi"] or 0))[:limit],
            "n": len(pool)}

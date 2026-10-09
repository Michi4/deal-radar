"""Value board: rank everything seen recently by measured perf/€, perf/W, raw marks.

No network: CPU extraction + cached benchmarks + kind classification only.
Unrated items are counted, not guessed.
"""
from __future__ import annotations

import time


def cached_cpu(cpu: str) -> dict | None:
    """PassMark entry from disk/memory cache only (None when never fetched)."""
    from . import benchmarks as _b
    key = "v2:" + cpu.strip().lower()
    mem = getattr(_b, "_mem", {})
    if key in mem:
        return mem[key]
    try:
        disk = _b._load()
        if key in disk:
            return disk[key]
    except Exception:
        pass
    return None


def collect(store, days: float = 14.0, fav_ids: set[str] | None = None) -> tuple[list[dict], int]:
    """All recently-seen listings + favorites, enriched from cache. Returns (items, unrated)."""
    from .decision import heuristic_decide
    from .scoring import extract_cpu
    cutoff = time.time() - days * 86400
    try:
        rows = store.db.execute(
            "SELECT id, title, price, currency, url, source, data FROM listings "
            "WHERE last_seen >= ? ORDER BY last_seen DESC LIMIT 20000", (cutoff,)).fetchall()
    except Exception:
        return [], 0
    favs = fav_ids if fav_ids is not None else set()
    items: list[dict] = []
    unrated = 0
    for lid, title, price, cur, url, src, data in rows:
        title = title or ""
        try:
            import json as _j
            blob = _j.loads(data or "{}")
            desc = blob.get("description", "") or ""
        except Exception:
            desc = ""
        cpu, _, _ = extract_cpu(f"{title}\n{desc}")
        bench = cached_cpu(cpu) if cpu else None
        multi = (bench or {}).get("multi")
        if not multi:
            unrated += 1
            continue
        single = (bench or {}).get("single")
        tdp = None
        try:
            tdp = float(str((bench or {}).get("tdp") or "").split()[0])
        except (TypeError, ValueError, IndexError):
            tdp = None
        try:
            kind = heuristic_decide(title, desc, price, "").get("kind", "offer")
        except Exception:
            kind = "offer"
        items.append({"id": lid, "title": title[:100], "price": price,
                      "currency": cur or "EUR", "url": url, "source": src,
                      "cpu": cpu, "multi": multi, "single": single, "tdp_w": tdp,
                      "kind": kind, "fav": lid in favs,
                      "ppe": round(multi / price, 1) if price else 0,
                      "ppw": round(multi / tdp, 1) if tdp else 0})
    return items, unrated


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

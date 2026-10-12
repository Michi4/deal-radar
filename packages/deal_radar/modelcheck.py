"""Free-model health checker: probe every candidate with a tiny exact-JSON task,
rank best-first. Persistence (store settings) is the caller's job."""
from __future__ import annotations

import os

TASK_SYSTEM = "Return ONLY JSON, nothing else."
TASK_USER = 'Reply {"ping": 1}'


def candidates() -> list[dict]:
    """Candidate pool. MODELCHECK_MODELS overrides (comma separated):
    `cli:<model>` for the opencode CLI, `cloud:<model>` or bare model for CLOUD_*."""
    raw = os.getenv("MODELCHECK_MODELS", "")
    url = os.getenv("CLOUD_API_URL", "")
    key = os.getenv("CLOUD_API_KEY", "")
    if raw:
        out: list[dict] = []
        for m in [x.strip() for x in raw.split(",") if x.strip()]:
            if m.startswith("cli:"):
                out.append({"kind": "cli", "model": m[4:]})
            else:
                out.append({"kind": "cloud", "url": url, "key": key,
                            "model": m.removeprefix("cloud:")})
        return out
    from .decision import _cli_model
    cands = [{"kind": "cloud", "url": url, "key": key, "model": m} for m in
             ("deepseek/deepseek-v4-flash-free", "tencent/hy3-free",
              "z-ai/glm-5.3-flash-free")]
    if _cli_model():
        cands.append({"kind": "cli", "model": _cli_model()})
    return cands


def ckey(cand: dict) -> str:
    return f"{cand.get('kind', '')}:{cand.get('url', '')}:{cand.get('model', '')}"


async def probe_one(cand: dict, timeout: float = 45.0) -> dict:
    """One tiny exact-JSON task. ok only on the exact answer (no key = honest fail)."""
    import time as _t

    from . import decision as D
    key = ckey(cand)
    t0 = _t.time()
    try:
        if cand.get("kind") == "cli":
            out = await D._cli_json(TASK_SYSTEM, TASK_USER, timeout=timeout)
        else:
            if not (cand.get("url") and cand.get("key")):
                return {"candidate": key, "ok": False, "latency": 0.0,
                        "note": "no url/key configured"}
            out = await D._post_chat(cand["url"], cand["key"], cand["model"],
                                     TASK_SYSTEM, TASK_USER, 60, timeout=timeout)
            if isinstance(out, dict) and (out.get("__error") or out.get("__rate_limited")):
                return {"candidate": key, "ok": False,
                        "latency": round(_t.time() - t0, 2),
                        "note": str(out.get("__error") or "rate limited")[:100]}
        dt = round(_t.time() - t0, 2)
        if isinstance(out, dict) and out.get("ping") == 1:
            return {"candidate": key, "ok": True, "latency": dt, "note": "exact answer"}
        return {"candidate": key, "ok": False, "latency": dt,
                "note": f"wrong shape: {str(out)[:80]}"}
    except Exception as e:
        return {"candidate": key, "ok": False, "latency": round(_t.time() - t0, 2),
                "note": str(e)[:100]}


async def probe_all(timeout_each: float = 45.0) -> list[dict]:
    """Probe the whole pool concurrently. Never raises (each probe is guarded)."""
    import asyncio as _aio
    import time as _t
    results = await _aio.gather(*[probe_one(c, timeout_each) for c in candidates()])
    out = [dict(r) for r in results]
    for r in out:
        r["ts"] = _t.time()
    return out


async def warmup_benchmarks(store, cap: int = 120) -> int:
    """Rebuild the PassMark disk cache after deploys: distinct CPUs from recent
    listings (title+description, exact mentions AND family-seed estimates),
    most-frequent uncached first. Cached hits free, uncached fetched politely.
    Vague labels (no model number) are skipped — PassMark can't score them.
    Returns warmed count."""
    import asyncio as _aio
    import re as _re
    import time as _t
    from collections import Counter

    from . import benchmarks as _b
    from .scoring import resolve_cpu_with_seeds
    try:
        rows = store.db.execute(
            "SELECT title, data FROM listings WHERE last_seen >= ? LIMIT 20000",
            (_t.time() - 14 * 86400,)).fetchall()
    except Exception:
        return 0
    freq: Counter = Counter()
    for title, data in rows:
        try:
            import json as _j
            desc = (_j.loads(data or "{}") or {}).get("description", "") or ""
        except Exception:
            desc = ""
        try:
            cpu, _, _, _, _ = resolve_cpu_with_seeds(f"{title or ''}\n{desc}")
        except Exception:
            continue
        if cpu and _re.search(r"\d{3,}", cpu):
            freq[cpu] += 1
    warmed = 0
    for cpu, _ in freq.most_common():
        if warmed >= cap:
            break
        try:
            from .benchmarks import cached_cpu as _cc
            if _cc(cpu):
                continue
            await _aio.to_thread(_b.fetch_passmark_cpu, cpu)
            warmed += 1
        except Exception:
            pass
        try:
            await _aio.sleep(1.0)  # polite: ~1 req/s max on cold misses
        except Exception:
            pass
    return warmed

"""FastAPI: searches, live SSE stream, favorites, drivers, metrics, health.
Run: PYTHONPATH=packages:drivers uvicorn api.main:app --reload (from apps/api)
Generic engine: intent DSL works for products, jobs, housing, anything with listings.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "drivers"))

from fastapi import FastAPI, Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from deal_radar import metrics
from deal_radar.driver_sdk import DriverRegistry
from deal_radar.notifications import notifier_from_env
from deal_radar.orchestrator import run_search
from deal_radar.store import Store

app = FastAPI(title="deal-radar", version="0.1.0")

# in-app auth + rate limit (defense in depth behind Authelia/basic-auth at the edge)
import time as _t

API_KEY = os.getenv("API_KEY", "")
_hits: dict[str, list[float]] = {}
RATE_PER_MIN = int(os.getenv("RATE_PER_MIN", "120"))


@app.middleware("http")
async def _gate(request: Request, call_next):
    if API_KEY and request.url.path not in ("/health",) and request.headers.get("x-api-key") != API_KEY:
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    ip = (request.client.host if request.client else "?") if request.url.path.startswith(("/searches", "/stream")) else None
    if ip:
        now = _t.time()
        lst = [t for t in _hits.get(ip, []) if now - t < 60]
        if len(lst) >= RATE_PER_MIN:
            return JSONResponse({"detail": "rate limited"}, status_code=429)
        lst.append(now)
        _hits[ip] = lst
    return await call_next(request)
registry = DriverRegistry()
store = Store(os.getenv("DB_PATH", "data/dealradar.db"))
notifier = notifier_from_env(os.environ)
SEARCHES: dict[str, dict] = {}
EVENT_LOG: list[dict] = []
SEEN_IDS: dict[str, set[str]] = {}
LAST_RUN: dict[str, float] = {}
RESULT_CACHE: dict[str, tuple[float, dict]] = {}
CACHE_TTL = float(os.getenv("CACHE_TTL_S", "120"))


def default_sources() -> list[str]:
    import os as _os
    out = []
    for d in registry.manifests():
        if d.id == "ebay" and not _os.getenv("EBAY_OAUTH_TOKEN"):
            continue  # needs credentials; user said ignore for now
        out.append(d.id)
    return out or registry.ids()


def _intent_key(intent: dict) -> str:
    import hashlib
    return hashlib.sha256(json.dumps(intent, sort_keys=True, default=str).encode()).hexdigest()[:32]


async def _run_cached(intent: dict, force: bool = False) -> dict:
    key = _intent_key(intent)
    now = time.time()
    if not force and key in RESULT_CACHE and now - RESULT_CACHE[key][0] < CACHE_TTL:
        metrics.inc("cache_hits")
        return RESULT_CACHE[key][1]
    metrics.inc("cache_miss")
    out = await run_search(intent, registry, store, notifier)
    RESULT_CACHE[key] = (now, out)
    return out


from deal_radar.notify_rules import rules_ok as _rules_ok


async def _watcher() -> None:
    """Live loop: re-poll watched searches, push new-match events to SSE + notifiers."""
    await asyncio.sleep(5)
    while True:
        try:
            for sid, intent in list(SEARCHES.items()):
                if not intent.get("watch"):
                    continue
                interval = max(45, int(intent.get("poll_interval_s", 300)))
                if time.time() - LAST_RUN.get(sid, 0) < interval:
                    continue
                LAST_RUN[sid] = time.time()
                out = await _run_cached(intent, force=True)
                seen = SEEN_IDS.setdefault(sid, set())
                fresh = [r for r in out.get("results", []) if r["listing"]["id"] not in seen]
                for r in out.get("results", []):
                    seen.add(r["listing"]["id"])
                notify_on = intent.get("notify_on", ["new_top", "price_drop"])
                rules = intent.get("notify_rules", [])
                for r in fresh:
                    if r["lane"] in ("hidden",):
                        continue
                    if "new_top" in notify_on and r["lane"] in ("top", "good") and r["final_score"] >= 0.5 \
                            and _rules_ok(rules, "new_match", r=r):
                        ev = {"kind": "new_match", "listing_id": r["listing"]["id"],
                              "title": r["listing"]["title"], "price": r["listing"]["price"],
                              "url": r["listing"]["url"], "score": r["final_score"]}
                        EVENT_LOG.append(ev)
                        await notifier.send(
                            f"New match {r['final_score']:.2f}: {(r['listing']['title'] or '')[:80]}",
                            f"{r['listing']['price']} {r['listing']['currency']} @ {r['listing']['source']} "
                            f"({r['listing']['location']}) risk {r['risk']['score']:.0%}\n{r['listing']['url']}",
                            {"url": r["listing"]["url"]})
                EVENT_LOG.extend(out.get("events", []))  # price notifies are sent (rule-gated) by the orchestrator itself
        except Exception as e:
            print(f"[watcher] {e}", flush=True)
        await asyncio.sleep(15)


@app.on_event("startup")
async def _start_watcher():
    asyncio.create_task(_watcher())


def load_drivers() -> None:
    import json as _json

    from ebay.driver import EbayDriver
    from kleinanzeigen.driver import KleinanzeigenDriver
    from ricardo.driver import RicardoDriver
    from shpock.driver import ShpockDriver
    from vinted.driver import VintedDriver
    from willhaben.driver import WillhabenDriver

    from deal_radar.driver_sdk import transport_from_config
    cfg = {}
    try:
        cfg = _json.loads(os.getenv("TRANSPORTS_JSON", "{}"))
    except Exception:
        cfg = {}
    registry.register(EbayDriver(transport_from_config(cfg.get("ebay"))))
    registry.register(WillhabenDriver(transport_from_config(cfg.get("willhaben"))))
    registry.register(KleinanzeigenDriver(transport_from_config(cfg.get("kleinanzeigen"))))
    registry.register(VintedDriver(transport_from_config(cfg.get("vinted"))))
    registry.register(ShpockDriver(transport_from_config(cfg.get("shpock"))))
    registry.register(RicardoDriver(transport_from_config(cfg.get("ricardo"))))


load_drivers()
try:
    from deal_radar import ailab as _ailab
    _loaded = _ailab.load_custom_enrichers()
    if _loaded:
        print(f"[lab] loaded persisted enrichers: {_loaded}", flush=True)
except Exception as _e:
    print(f"[lab] {type(_e).__name__}", flush=True)
for _sid, _intent in store.load_searches().items():
    SEARCHES[_sid] = _intent
    if _intent.get("watch"):
        LAST_RUN[_sid] = 0  # re-poll watched searches right after restart
static_dir = Path(__file__).resolve().parents[2] / "web"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


class SearchIntent(BaseModel):
    keywords: str = ""
    category: str = ""
    sources: list[str] | None = None
    hard: dict = {}
    blacklist: list[dict] = []
    whitelist: list[dict] = []
    required: list[dict] = []  # must-contain (AND): every rule must match
    risk: dict = {}
    ranking: dict | None = None
    enrich: bool = True
    limit: int = 20
    max_pages: int | None = None  # per-source page cap; empty = walk to exhaustion
    watch: bool = False
    poll_interval_s: int = 300
    notify_on: list[str] = ["new_top", "price_drop"]
    notify_rules: list[dict] = []  # e.g. {"kind":"price_drop","min_drop_pct":15},{"kind":"new_match","max_risk":0.2}
    max_distance_km: float | None = None
    require_pickup: bool = False
    require_shipping: bool = False


@app.get("/", response_class=HTMLResponse)
def index():
    html = Path(__file__).resolve().parents[2] / "web" / "index.html"
    return html.read_text() if html.exists() else "<h1>deal-radar up. See /docs</h1>"


@app.get("/health")
def health():
    return {"ok": True, "drivers": registry.ids(), "time": time.time()}


@app.get("/drivers")
def drivers():
    out = []
    for m in registry.manifests():
        d = m.model_dump()
        reqs = {"ebay": ["EBAY_OAUTH_TOKEN"]}.get(m.id, [])
        d["requires"] = reqs
        d["configured"] = all(os.getenv(r) for r in reqs)
        out.append(d)
    return out


@app.get("/metrics")
def metrics_ep():
    return PlainTextResponse(metrics.prometheus())


@app.get("/metrics.json")
def metrics_json():
    return {"metrics": metrics.snapshot(), "drivers": {d: registry.get(d).health.model_dump() for d in registry.ids()},
            "searches": len(SEARCHES), "events": len(EVENT_LOG),
            "watchlist": [{"id": sid, "keywords": i.get("keywords", ""), "watch": bool(i.get("watch", False)),
                           "sources": i.get("sources", [])} for sid, i in SEARCHES.items()],
            "events_tail": EVENT_LOG[-30:]}


@app.get("/admin", response_class=HTMLResponse)
def admin():
    html = Path(__file__).resolve().parents[2] / "web" / "admin.html"
    return html.read_text() if html.exists() else "<h1>admin missing</h1>"


class NLQuery(BaseModel):
    text: str
    sources: list[str] | None = None
    watch: bool = False
    poll_interval_s: int = 300
    limit: int = 20
    max_pages: int | None = None
    ocr: bool = True
    benchmarks: bool = True
    vision: bool = True
    details: bool = True


@app.post("/searches/nl")
async def create_nl_search(q: NLQuery):
    from deal_radar.decision import nl_to_intent
    parsed = await nl_to_intent(q.text)
    models = (parsed.get("models", []) or [])[:6]  # bound fan-out
    queries = models or [parsed.get("keywords", q.text)]
    intents = []
    for kw in queries:
        intents.append({"keywords": kw, "category": parsed.get("category", ""),
                        "sources": q.sources or default_sources(),
                        "hard": {"min_match": 0.2, **(parsed.get("hard", {}) or {})},
                        "blacklist": parsed.get("blacklist", []), "whitelist": [], "risk": {},
                        "ranking": None, "attributes": parsed.get("attributes", {}),
                        "models": parsed.get("models", []) or [],
                        "required": parsed.get("required", []),
                        "enrich": True, "max_pages": q.max_pages, "ocr": q.ocr, "benchmarks": q.benchmarks,
                        "vision": q.vision, "details": q.details,
                        "limit": max(6, q.limit // max(1, len(queries))),
                        "watch": False, "poll_interval_s": q.poll_interval_s,
                        "notify_on": ["new_top", "price_drop"]})
    base = {"keywords": parsed.get("keywords", q.text), "category": parsed.get("category", ""),
            "sources": q.sources or default_sources(), "hard": {"min_match": 0.2, **(parsed.get("hard", {}) or {})},
            "blacklist": parsed.get("blacklist", []), "whitelist": [], "risk": {},
            "ranking": None, "attributes": parsed.get("attributes", {}),
            "models": parsed.get("models", []) or [],
            "required": parsed.get("required", []),
            "enrich": True, "max_pages": q.max_pages, "ocr": q.ocr, "benchmarks": q.benchmarks,
            "vision": q.vision, "details": q.details,
            "limit": q.limit, "watch": q.watch,
            "poll_interval_s": q.poll_interval_s, "notify_on": ["new_top", "price_drop"]}
    return await _start_job(intents, {"parsed": parsed, "base": base, "subqueries": queries,
                                      "limit": q.limit, "watch": q.watch})


def _merge_outs(outs: list[dict], limit: int) -> dict:
    import statistics as _st
    seen: set[str] = set()
    merged: list[dict] = []
    events: list[dict] = []
    errors: dict = {}
    filt = 0
    for o in outs:
        filt += o.get("filtered_out", 0)
        events.extend(o.get("events", []))
        errors.update(o.get("driver_errors", {}))
        for r in o.get("results", []):
            lid = r["listing"]["id"]
            if lid not in seen:
                seen.add(lid)
                merged.append(r)
    merged.sort(key=lambda r: r.get("final_score", 0), reverse=True)
    merged = merged[:limit]
    _mp = sorted(r["listing"]["price"] for r in merged if r["listing"].get("price") is not None)
    return {"results": merged, "events": events, "driver_errors": errors,
            "filtered_out": filt, "median": _st.median(_mp) if len(_mp) >= 3 else None}


JOBS: dict[str, dict] = {}


async def _start_job(intents: list[dict], meta: dict) -> dict:
    sid = f"s_{int(time.time() * 1000)}"
    JOBS[sid] = {"status": "running", "done": 0, "total": len(intents),
                 "intent": meta.get("base", intents[0] if intents else {}),
                 "parsed": meta.get("parsed"), "subqueries": meta.get("subqueries", [])}
    asyncio.create_task(_run_job(sid, intents, meta))
    return {"id": sid, "status": "running", "total": len(intents)}


async def _run_job(sid: str, intents: list[dict], meta: dict) -> None:
    try:
        outs = []
        for i, data in enumerate(intents):
            JOBS[sid]["done"] = i
            outs.append(await _run_cached(data, force=True))
        JOBS[sid]["done"] = len(intents)
        merged = _merge_outs(outs, meta.get("limit", 20))
        base = meta.get("base", intents[0] if intents else {})
        SEARCHES[sid] = base
        store.save_search(sid, base)
        LAST_RUN[sid] = time.time()
        SEEN_IDS[sid] = {r["listing"]["id"] for r in merged["results"]}
        store.save_results(sid, merged["results"])
        EVENT_LOG.extend(merged["events"])
        EVENT_LOG.append({"kind": "search_done", "listing_id": sid,
                          "title": f"search finished: {len(merged['results'])} results"})
        JOBS[sid].update({"status": "done", "result": merged})
        if base.get("watch") or meta.get("notify_done"):
            await notifier.send(f"Search done: {len(merged['results'])} results",
                                f"{base.get('keywords', '')} :: {len(merged['results'])} hits, "
                                f"{merged['filtered_out']} filtered", {"url": "/?sid=" + sid})
    except Exception as e:
        JOBS[sid].update({"status": "error", "error": f"{type(e).__name__}: {e}"})


@app.post("/searches")
async def create_search(intent: SearchIntent):
    data = intent.model_dump()
    if not data["sources"]:
        data["sources"] = default_sources()
    # location/delivery shorthand -> hard rules (fully inspectable in stored intent)
    rules = list((data.get("hard") or {}).get("rules", []) or [])
    if data.get("max_distance_km") is not None:
        rules.append({"field": "distance_km", "op": "lt", "value": data["max_distance_km"]})
    if data.get("require_pickup"):
        rules.append({"field": "pickup", "op": "equals", "value": True})
    if data.get("require_shipping"):
        rules.append({"field": "shipping_available", "op": "equals", "value": True})
    data["hard"] = {**(data.get("hard") or {}), "rules": rules}
    # multi-query: "rtx 4080; rtx 4070 ti super" -> parallel sub-searches, merged
    parts = [p.strip() for p in (data.get("keywords", "") or "").split(";") if p.strip()]
    if len(parts) > 1:
        intents = [{**data, "keywords": p, "watch": False} for p in parts[:6]]
        return await _start_job(intents, {"base": {**data, "watch": data.get("watch", False)},
                                          "subqueries": parts[:6], "limit": data.get("limit", 20),
                                          "watch": data.get("watch", False), "notify_done": True})
    return await _start_job([data], {"base": data, "limit": data.get("limit", 20),
                                     "watch": data.get("watch", False), "notify_done": True})


@app.get("/searches")
def list_searches():
    return {"searches": store.list_searches()}


@app.post("/searches/{sid}/redo")
async def redo_search(sid: str):
    intent = SEARCHES.get(sid)
    if intent is None:
        try:
            row = store.db.execute("SELECT intent FROM searches WHERE id=?", (sid,)).fetchone()
            import json as _j
            intent = _j.loads(row[0]) if row else None
        except Exception:
            intent = None
    if not intent:
        return {"error": "unknown search id"}
    from copy import deepcopy
    return await _start_job([deepcopy(intent)], {"base": deepcopy(intent), "limit": intent.get("limit", 20),
                                                "watch": intent.get("watch", False), "notify_done": True})


@app.get("/searches/{sid}")
async def get_search(sid: str):
    job = JOBS.get(sid)
    if job is not None:
        if job["status"] == "running":
            return {"id": sid, "status": "running", "done": job["done"], "total": job["total"]}
        if job["status"] == "error":
            return {"id": sid, "status": "error", "error": job.get("error")}
        out = job.get("result", {})
        return {"id": sid, "status": "done", "parsed": job.get("parsed"),
                "subqueries": job.get("subqueries", []), **out}
    intent = SEARCHES.get(sid)  # persisted from earlier session: re-run cached
    if not intent:
        return {"error": "unknown search id"}
    out = await _run_cached(intent)
    EVENT_LOG.extend(out.get("events", []))
    return {"id": sid, "status": "done", "cached": True, **out}


@app.get("/stream")
async def stream(request: Request):
    """SSE live feed: new matches + price/desc/image change events."""
    async def gen():
        last = 0
        while True:
            if await request.is_disconnected():
                break
            while last < len(EVENT_LOG):
                ev = EVENT_LOG[last]
                last += 1
                yield f"data: {json.dumps(ev)}\n\n"
            yield ": keep-alive\n\n"
            await asyncio.sleep(2)
    return StreamingResponse(gen(), media_type="text/event-stream")


@app.delete("/searches/{sid}")
def delete_search(sid: str):
    SEARCHES.pop(sid, None)
    SEEN_IDS.pop(sid, None)
    LAST_RUN.pop(sid, None)
    store.delete_search(sid)
    return {"ok": True}


class LabRequest(BaseModel):
    kind: str = "enricher"
    instruction: str = ""
    publish: bool = False


class FactOverride(BaseModel):
    field: str = "cpu"
    value: str = ""


@app.post("/listings/{lid}/facts")
def set_fact(lid: str, f: FactOverride):
    from urllib.parse import unquote
    lid = unquote(lid)
    store.set_fact(lid, f.field, f.value, by="user")
    return {"ok": True, "listing": lid, "field": f.field, "value": f.value}


@app.get("/listings/{lid}/facts")
def get_facts(lid: str):
    from urllib.parse import unquote
    return {"listing": unquote(lid), "facts": store.get_facts(unquote(lid))}


@app.get("/listings/{lid}/history")
def listing_history(lid: str):
    """Version timeline for a tracked item: price/desc/image observations."""
    from urllib.parse import unquote
    lid = unquote(lid)
    rows = store.db.execute(
        "SELECT ts, kind, old_value, new_value FROM observations WHERE listing_id=? ORDER BY ts",
        (lid,)).fetchall()
    return {"listing": lid, "history": [
        {"ts": r[0], "kind": r[1], "old": r[2], "new": r[3]} for r in rows]}


@app.get("/lab/status")
def lab_status():
    from deal_radar.enrich import REGISTRY
    from deal_radar.registry import installed
    return {"enabled": bool(os.getenv("LAB_ENABLED")), "enrichers": sorted(REGISTRY.keys()),
            "drivers": installed()}


@app.get("/marketplace")
def marketplace():
    """Public plugin/driver marketplace index (remote versioned JSON, PR-contributed)."""
    from deal_radar.registry import load_index
    try:
        idx = load_index()
    except Exception:
        idx = {"drivers": [], "enrichers": []}
    if not idx.get("drivers"):
        import json as _j
        p = Path(__file__).resolve().parents[2] / "marketplace" / "index.json"
        idx = _j.loads(p.read_text()) if p.exists() else {"drivers": [], "enrichers": []}
    from deal_radar.enrich import REGISTRY
    from deal_radar.registry import installed
    inst = set(installed())
    for d in idx.get("drivers", []):
        d["installed"] = d["id"] in inst
        reqs = d.get("requires", [])
        d["configured"] = all(os.getenv(r) for r in reqs)
    for e in idx.get("enrichers", []):
        e["installed"] = e["id"] in REGISTRY or e.get("source") == "builtin"
    return idx


class InstallRequest(BaseModel):
    id: str = ""


@app.post("/marketplace/install")
def marketplace_install(req: InstallRequest):
    """Single-click install from the marketplace index (checksummed + contract-checked)."""
    import json as _j
    p = Path(__file__).resolve().parents[2] / "marketplace" / "index.json"
    idx = _j.loads(p.read_text()) if p.exists() else {"drivers": []}
    entry = next((d for d in idx.get("drivers", []) if d["id"] == req.id), None)
    if not entry:
        return {"ok": False, "error": f"unknown marketplace id: {req.id}"}
    if entry.get("source") == "builtin":
        return {"ok": True, "installed": req.id, "note": "built in — enable per search"}
    from deal_radar.registry import install
    return install(entry)


@app.get("/notifications/status")
def notifications_status():
    chans = []
    if os.getenv("SIGNAL_NUMBER"):
        chans.append({"type": "signal", "target": "***" + os.getenv("SIGNAL_NUMBER", "")[-4:]})
    if os.getenv("NTFY_TOPIC_URL"):
        chans.append({"type": "ntfy"})
    if os.getenv("WEBHOOK_URL"):
        chans.append({"type": "webhook"})
    chans.append({"type": "log"})
    extra = []
    if os.getenv("NOTIFIERS_JSON"):
        try:
            import json as _j
            extra = [s.get("type", "?") for s in _j.loads(os.getenv("NOTIFIERS_JSON", "[]"))]
        except Exception:
            pass
    return {"channels": chans, "extra": extra}


@app.post("/lab/build")
async def lab_build(req: LabRequest):
    if not os.getenv("LAB_ENABLED"):
        return {"ok": False, "error": "LAB_ENABLED=0 (code-writing disabled)"}
    from deal_radar import ailab
    out = await ailab.generate(req.kind, req.instruction)
    if out.get("ok") and req.publish:
        out["pr"] = await lab_publish(out)
    return out


async def lab_publish(build: dict) -> dict:
    """Upload generated plugin to GitHub and open a PR (needs GH_TOKEN + LAB_PUBLISH=1)."""
    import base64
    tok, repo = os.getenv("GH_TOKEN", ""), os.getenv("LAB_REPO", "Michi4/deal-radar")
    if not tok or not os.getenv("LAB_PUBLISH"):
        return {"ok": False, "error": "GH_TOKEN/LAB_PUBLISH not set — code saved locally only"}
    try:
        did = build.get("id", "custom")
        branch = f"lab/{build.get('kind')}-{did}"
        async with httpx.AsyncClient(timeout=30) as c:
            h = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}
            base = (await c.get(f"https://api.github.com/repos/{repo}", headers=h)).json().get("default_branch", "main")
            sha = (await c.get(f"https://api.github.com/repos/{repo}/git/ref/heads/{base}", headers=h)).json()["object"]["sha"]
            await c.post(f"https://api.github.com/repos/{repo}/git/refs", headers=h,
                         json={"ref": f"refs/heads/{branch}", "sha": sha})
            from pathlib import Path as _P
            rel = _P(build["path"]).relative_to(_P.cwd()).as_posix() if _P(build["path"]).is_absolute() else build["path"]
            content = _P(build["path"]).read_bytes() if _P(build["path"]).exists() else b""
            await c.put(f"https://api.github.com/repos/{repo}/contents/{rel}", headers=h,
                        json={"message": f"feat(lab): {build.get('kind')} {did}",
                              "content": base64.b64encode(content).decode(), "branch": branch})
            pr = (await c.post(f"https://api.github.com/repos/{repo}/pulls", headers=h,
                               json={"title": f"feat(lab): {build.get('kind')} {did}",
                                     "head": branch, "base": base,
                                     "body": "AI-generated via /lab/build. Contract-checked locally."})).json()
            return {"ok": True, "pr": pr.get("html_url")}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@app.get("/searches/{sid}/compare")
async def compare(sid: str):
    """Group a search's results by product model: source × price × risk comparison table."""
    import re as _re
    intent = SEARCHES.get(sid)
    if not intent:
        return {"error": "unknown search id"}
    out = await _run_cached(intent)
    groups: dict[str, list] = {}
    for r in out.get("results", []):
        models = intent.get("models", []) or []
        title = r["listing"]["title"] or ""
        norm = _re.sub(r"[^a-z0-9]+", "", title.lower())
        key = next((m for m in models
                    if _re.sub(r"[^a-z0-9]+", "", m.lower()) in norm),
                   (title[:50] or "unknown"))
        groups.setdefault(key, []).append({
            "source": r["listing"]["source"], "price": r["listing"]["price"],
            "currency": r["listing"]["currency"], "location": r["listing"]["location"],
            "url": r["listing"]["url"], "risk": r["risk"]["score"],
            "score": r["final_score"], "lane": r["lane"],
            "cpu": next((e["value"] for e in r.get("enrichments", []) if e["field"] == "cpu"), None),
            "benchmark": next((e["value"] for e in r.get("enrichments", []) if e["field"] == "cpu_benchmark"), None)})
    for rows in groups.values():
        rows.sort(key=lambda x: (x["price"] is None, x["price"]))
    return {"id": sid, "groups": groups}


@app.post("/favorites/{listing_id}")
def fav(listing_id: str, note: str = ""):
    store.favorite(listing_id, note)
    return {"ok": True, "favorite": listing_id}


@app.delete("/favorites/{listing_id}")
def unfav(listing_id: str):
    store.unfavorite(listing_id)
    return {"ok": True}


@app.get("/favorites")
def favs():
    return store.favorites_with_history()


@app.get("/market")
def market(limit: int = 60, offset: int = 0, source: str = ""):
    """Marketplace view: recent live inventory across all searches (newest first)."""
    q = "SELECT id, source, url, title, price, currency, last_seen, data FROM listings"
    args: list = []
    if source:
        q += " WHERE source=?"
        args.append(source)
    q += " ORDER BY last_seen DESC LIMIT ? OFFSET ?"
    args += [max(1, min(limit, 200)), max(0, offset)]
    rows = store.db.execute(q, args).fetchall()
    import json as _j
    items = []
    for lid, src, url, title, price, cur, seen, data in rows:
        try:
            d = _j.loads(data)
            imgs = d.get("images", [])[:1]
        except Exception:
            imgs = []
        items.append({"id": lid, "source": src, "url": url, "title": title, "price": price,
                      "currency": cur, "last_seen": seen, "image": imgs[0] if imgs else None,
                      "favorite": store.is_favorite(lid)})
    return {"items": items, "limit": limit, "offset": offset}

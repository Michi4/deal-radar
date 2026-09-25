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

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "drivers"))

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from deal_radar.driver_sdk import DriverRegistry
from deal_radar.orchestrator import run_search
from deal_radar.store import Store
from deal_radar.notifications import notifier_from_env
from deal_radar import metrics

app = FastAPI(title="deal-radar", version="0.1.0")
registry = DriverRegistry()
store = Store(os.getenv("DB_PATH", "data/dealradar.db"))
notifier = notifier_from_env(os.environ)
SEARCHES: dict[str, dict] = {}
EVENT_LOG: list[dict] = []
SEEN_IDS: dict[str, set[str]] = {}
LAST_RUN: dict[str, float] = {}
RESULT_CACHE: dict[str, tuple[float, dict]] = {}
CACHE_TTL = float(os.getenv("CACHE_TTL_S", "120"))


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
                for r in fresh:
                    if r["lane"] in ("hidden",):
                        continue
                    if "new_top" in notify_on and r["lane"] in ("top", "good") and r["final_score"] >= 0.5:
                        ev = {"kind": "new_match", "listing_id": r["listing"]["id"],
                              "title": r["listing"]["title"], "price": r["listing"]["price"],
                              "url": r["listing"]["url"], "score": r["final_score"]}
                        EVENT_LOG.append(ev)
                        await notifier.send(
                            f"New match {r['final_score']:.2f}: {(r['listing']['title'] or '')[:80]}",
                            f"{r['listing']['price']} {r['listing']['currency']} @ {r['listing']['source']} "
                            f"({r['listing']['location']}) risk {r['risk']['score']:.0%}\n{r['listing']['url']}",
                            {"url": r["listing"]["url"]})
                for ev in out.get("events", []):
                    EVENT_LOG.append(ev)
                    if ev.get("kind") == "price_drop" or (ev.get("kind") == "price" and "notify_on" in intent and "price_drop" in notify_on):
                        pass  # price-change notifies already handled in orchestrator via store diff
        except Exception as e:  # noqa: BLE001 - watcher never dies
            print(f"[watcher] {e}", flush=True)
        await asyncio.sleep(15)


@app.on_event("startup")
async def _start_watcher():
    asyncio.create_task(_watcher())


def load_drivers() -> None:
    from ebay.driver import EbayDriver
    from willhaben.driver import WillhabenDriver
    from kleinanzeigen.driver import KleinanzeigenDriver
    from deal_radar.driver_sdk import transport_from_config
    import json as _json
    cfg = {}
    try:
        cfg = _json.loads(os.getenv("TRANSPORTS_JSON", "{}"))
    except Exception:
        cfg = {}
    registry.register(EbayDriver(transport_from_config(cfg.get("ebay"))))
    registry.register(WillhabenDriver(transport_from_config(cfg.get("willhaben"))))
    registry.register(KleinanzeigenDriver(transport_from_config(cfg.get("kleinanzeigen"))))


load_drivers()
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
    risk: dict = {}
    ranking: dict | None = None
    enrich: bool = True
    limit: int = 20
    watch: bool = False
    poll_interval_s: int = 300
    notify_on: list[str] = ["new_top", "price_drop"]
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
    return [m.model_dump() for m in registry.manifests()]


@app.get("/metrics")
def metrics_ep():
    return PlainTextResponse(metrics.prometheus())


@app.get("/metrics.json")
def metrics_json():
    return {"metrics": metrics.snapshot(), "drivers": {d: registry.get(d).health.model_dump() for d in registry.ids()},
            "searches": len(SEARCHES), "events": len(EVENT_LOG)}


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


@app.post("/searches/nl")
async def create_nl_search(q: NLQuery):
    from deal_radar.decision import nl_to_intent
    parsed = await nl_to_intent(q.text)
    models = (parsed.get("models", []) or [])[:6]  # bound fan-out
    queries = models or [parsed.get("keywords", q.text)]
    outs: list[dict] = []
    for kw in queries:
        data = {"keywords": kw, "category": parsed.get("category", ""),
                "sources": q.sources or registry.ids(), "hard": parsed.get("hard", {}),
                "blacklist": parsed.get("blacklist", []), "whitelist": [], "risk": {},
                "ranking": None, "attributes": parsed.get("attributes", {}),
                "models": parsed.get("models", []) or [],
                "enrich": True, "limit": max(6, q.limit // max(1, len(queries))),
                "watch": False, "poll_interval_s": q.poll_interval_s,
                "notify_on": ["new_top", "price_drop"]}
        outs.append(await _run_cached(data, force=True))
    # merge + dedupe across model queries
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
    merged = merged[:q.limit]
    sid = f"s_{int(time.time() * 1000)}"
    base = {"keywords": parsed.get("keywords", q.text), "category": parsed.get("category", ""),
            "sources": q.sources or registry.ids(), "hard": parsed.get("hard", {}),
            "blacklist": parsed.get("blacklist", []), "whitelist": [], "risk": {},
            "ranking": None, "attributes": parsed.get("attributes", {}),
            "models": parsed.get("models", []) or [],
            "enrich": True, "limit": q.limit, "watch": q.watch,
            "poll_interval_s": q.poll_interval_s, "notify_on": ["new_top", "price_drop"]}
    SEARCHES[sid] = base
    store.save_search(sid, base)
    LAST_RUN[sid] = time.time()
    SEEN_IDS[sid] = {r["listing"]["id"] for r in merged}
    EVENT_LOG.extend(events)
    return {"id": sid, "parsed": parsed, "results": merged, "events": events,
            "driver_errors": errors, "filtered_out": filt, "median": None,
            "sources": base["sources"], "subqueries": queries}


@app.post("/searches")
async def create_search(intent: SearchIntent):
    sid = f"s_{int(time.time() * 1000)}"
    data = intent.model_dump()
    if not data["sources"]:
        data["sources"] = registry.ids()
    # location/delivery shorthand -> hard rules (fully inspectable in stored intent)
    rules = list((data.get("hard") or {}).get("rules", []) or [])
    if data.get("max_distance_km") is not None:
        rules.append({"field": "distance_km", "op": "lt", "value": data["max_distance_km"]})
    if data.get("require_pickup"):
        rules.append({"field": "pickup", "op": "equals", "value": True})
    if data.get("require_shipping"):
        rules.append({"field": "shipping_available", "op": "equals", "value": True})
    data["hard"] = {**(data.get("hard") or {}), "rules": rules}
    SEARCHES[sid] = data
    store.save_search(sid, data)
    LAST_RUN[sid] = time.time()
    out = await _run_cached(data, force=True)
    SEEN_IDS[sid] = {r["listing"]["id"] for r in out.get("results", [])}
    EVENT_LOG.extend(out.get("events", []))
    return {"id": sid, **out}


@app.get("/searches/{sid}")
async def get_search(sid: str):
    intent = SEARCHES.get(sid)
    if not intent:
        return {"error": "unknown search id"}
    out = await _run_cached(intent)
    EVENT_LOG.extend(out.get("events", []))
    return {"id": sid, "cached": True, **out}


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

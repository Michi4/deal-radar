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
    poll_interval_s: int = 120


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


@app.post("/searches")
async def create_search(intent: SearchIntent):
    sid = f"s_{int(time.time() * 1000)}"
    data = intent.model_dump()
    if not data["sources"]:
        data["sources"] = registry.ids()
    SEARCHES[sid] = data
    out = await run_search(data, registry, store, notifier)
    EVENT_LOG.extend(out.get("events", []))
    return {"id": sid, **out}


@app.get("/searches/{sid}")
async def get_search(sid: str):
    intent = SEARCHES.get(sid)
    if not intent:
        return {"error": "unknown search id"}
    out = await run_search(intent, registry, store, notifier)
    EVENT_LOG.extend(out.get("events", []))
    return {"id": sid, **out}


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


@app.post("/favorites/{listing_id}")
def fav(listing_id: str, note: str = ""):
    store.favorite(listing_id, note)
    return {"ok": True, "favorite": listing_id}


@app.delete("/favorites/{listing_id}")
def unfav(listing_id: str):
    store.unfavorite(listing_id)
    return {"ok": True}

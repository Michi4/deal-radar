"""FastAPI: searches, live SSE stream, favorites, drivers, metrics, health.
Run: PYTHONPATH=packages:drivers:apps .venv/bin/python -m uvicorn api.main:app --app-dir apps (from repo root)
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
    RedirectResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from deal_radar import metrics
from deal_radar.driver_sdk import DriverRegistry
from deal_radar.notifications import notifier_from_env
from deal_radar.orchestrator import run_search
from deal_radar.store import Store

app = FastAPI(title="deal-radar", version="0.1.0")

# in-app auth + rate limit (defense in depth behind Authelia/basic-auth at the edge)
import hmac as _hmac
import time as _t

API_KEY = os.getenv("API_KEY", "")
LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD", "")
_hits: dict[str, list[float]] = {}
_login_hits: dict[str, list[float]] = {}
SESSIONS: dict[str, float] = {}  # token -> expiry ts
SESSION_TTL = 30 * 24 * 3600
RATE_PER_MIN = int(os.getenv("RATE_PER_MIN", "120"))


def _prune_sessions() -> None:
    now = _t.time()
    for tok in [t for t, exp in SESSIONS.items() if exp <= now]:
        SESSIONS.pop(tok, None)
    while len(SESSIONS) > 200:
        SESSIONS.pop(next(iter(SESSIONS)), None)
    while len(LAB_JOBS) > 50:
        LAB_JOBS.pop(next(iter(LAB_JOBS)), None)


def _logged_in(request: Request) -> bool:
    if not LOGIN_PASSWORD:
        return True
    tok = request.cookies.get("dr_session", "")
    exp = SESSIONS.get(tok)
    if exp and exp > _t.time():
        return True
    SESSIONS.pop(tok, None)
    return False


def _login_page(err: str = "") -> HTMLResponse:
    return HTMLResponse(
        "<!doctype html><html lang='en' class='dark'><head><meta charset='utf-8'/>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
        "<meta name='theme-color' content='#059669'/>"
        "<title>deal-radar — login</title>"
        "<style>:root{color-scheme:dark light}body{margin:0;min-height:100vh;display:flex;"
        "align-items:center;justify-content:center;background:#020617;color:#e2e8f0;"
        "font-family:system-ui,sans-serif}.card{background:#0f172a;border:1px solid #1e293b;"
        "border-radius:1rem;padding:2rem;min-width:min(22rem,90vw);text-align:center}"
        "h1{font-size:1.3rem;margin:.5rem 0 1.2rem;background:linear-gradient(90deg,#34d399,#6ee7b7);"
        "-webkit-background-clip:text;background-clip:text;color:transparent}"
        "input{width:100%;box-sizing:border-box;padding:.7rem .9rem;border-radius:.6rem;border:2px solid #334155;"
        "background:#020617;color:inherit;font-size:1rem;margin-bottom:.8rem}"
        "input:focus{outline:none;border-color:#34d399}"
        "button{width:100%;padding:.7rem;background:#059669;border:none;border-radius:.6rem;color:#fff;"
        "font-size:1rem;font-weight:700;cursor:pointer;min-height:44px}"
        ".err{color:#f87171;margin-bottom:.8rem}</style></head><body>"
        "<form class='card' method='post' action='/login'>"
        "<div style='font-size:2rem'>◎</div><h1>deal-radar</h1>"
        + (f"<div class='err'>{err}</div>" if err else "") +
        "<input type='password' name='password' placeholder='password' autocomplete='current-password' autofocus/>"
        "<button type='submit'>log in</button></form></body></html>")


_RL_PATHS = ("/searches", "/stream", "/lab", "/marketplace", "/favorites", "/listings", "/market")


@app.middleware("http")
async def _gate(request: Request, call_next):
    if API_KEY and request.url.path not in ("/health",) and not _hmac.compare_digest(
            request.headers.get("x-api-key", ""), API_KEY):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    path = request.url.path
    if LOGIN_PASSWORD and path not in ("/health", "/login", "/auth/status", "/static/favicon.svg"):
        if request.method == "GET" and path in ("/", "/admin"):
            if not _logged_in(request):
                return _login_page()
        elif path.startswith("/static/"):
            if not _logged_in(request):
                return JSONResponse({"detail": "login required"}, status_code=401)
        elif not _logged_in(request):
            return JSONResponse({"detail": "login required"}, status_code=401)
    if request.url.path.startswith(_RL_PATHS) or request.method in ("POST", "PUT", "PATCH", "DELETE"):
        ip = request.client.host if request.client else "?"
        now = _t.time()
        if len(_hits) > 5000:  # bound memory: drop stale buckets
            for k in [k for k, v in _hits.items() if not v or now - v[-1] > 60][:1000]:
                _hits.pop(k, None)
        lst = [t for t in _hits.get(ip, []) if now - t < 60]
        if len(lst) >= RATE_PER_MIN:
            return JSONResponse({"detail": "rate limited"}, status_code=429)
        lst.append(now)
        _hits[ip] = lst
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' https: data:; connect-src 'self'; "
        "frame-ancestors 'self'; base-uri 'self'; form-action 'self'")
    return resp
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


def _bounded_append(ev: dict) -> None:
    EVENT_LOG.append(ev)
    del EVENT_LOG[:-5000]


def _cache_evict() -> None:
    if len(RESULT_CACHE) > 200:
        for k in sorted(RESULT_CACHE, key=lambda k: RESULT_CACHE[k][0])[:len(RESULT_CACHE) - 200]:
            RESULT_CACHE.pop(k, None)
    # finished jobs: drop heavy payloads (status + snapshot-on-disk remain servable)
    done = [k for k, v in JOBS.items() if v.get("status") not in ("running", "paused")]
    for k in done[:max(0, len(done) - 300)]:
        JOBS[k].pop("result", None)
        JOBS[k].pop("partial", None)


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

FAV_POLL_S = int(os.getenv("FAV_POLL_S", "1800"))
_last_fav_poll = 0.0


def _fav_poll_s() -> int:
    try:
        return max(300, int(store.setting_get("fav_poll_s", str(FAV_POLL_S))))
    except Exception:
        return FAV_POLL_S


@app.get("/settings/tracking")
def tracking_settings():
    return {"fav_poll_min": _fav_poll_s() // 60}


class TrackingSettings(BaseModel):
    fav_poll_min: int = Field(ge=5, le=1440)


@app.put("/settings/tracking")
def tracking_settings_put(s: TrackingSettings):
    store.setting_set("fav_poll_s", str(s.fav_poll_min * 60))
    return {"ok": True, "fav_poll_min": s.fav_poll_min}


async def _track_favorites() -> None:
    """Snoty-style product tracking: re-fetch every saved product, version all changes."""
    global _last_fav_poll
    if time.time() - _last_fav_poll < _fav_poll_s():
        return
    _last_fav_poll = time.time()
    try:
        favs = store.favorites_with_history()
    except Exception:
        return
    for f in favs:
        lid = f.get("listing_id")
        url = f.get("url") or ""
        try:
            row = store.db.execute("SELECT source, url FROM listings WHERE id=?", (lid,)).fetchone()
        except Exception:
            continue
        if not row:
            continue
        src, durl = row[0], row[1] or url
        d = registry.get(src)
        if d is None or "fetch_detail" not in (d.manifest.capabilities or []):
            continue
        try:
            det = await d.fetch_detail(durl)
        except Exception:
            metrics.inc("favtrack_errors")
            continue
        if not det:
            continue
        det.id = lid  # keep stable id so history accumulates on the saved item
        try:
            for c in store.upsert(det):
                ev = {"kind": ("fav_" + c["kind"]), "listing_id": lid, "url": durl,
                      "title": det.title, "price": det.price}
                EVENT_LOG.append(ev)
                try:
                    await notifier.send(
                        f"Tracked change ({c['kind']}): {(det.title or '')[:60]}",
                        f"{c['kind']}: {str(c.get('old'))[:80]} → {str(c.get('new'))[:80]}\n{durl}",
                        {"url": durl})
                except Exception:
                    pass
        except Exception:
            continue


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
            try:
                await _track_favorites()
            except Exception:
                metrics.inc("watcher_errors")
        except Exception as e:
            metrics.inc("watcher_errors")
            print(f"[watcher] {type(e).__name__}: {e}", flush=True)
        try:
            _cache_evict()
            del EVENT_LOG[:-5000]
            _prune_sessions()
        except Exception:
            pass
        await asyncio.sleep(15)


@app.on_event("startup")
async def _start_watcher():
    try:
        n = store.job_interrupt_stale()
        if n:
            print(f"[startup] marked {n} stale running job(s) interrupted")
    except Exception:
        pass
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
        try:
            _snap = store.load_snapshot(_sid) or {}
            SEEN_IDS[_sid] = {r["listing"]["id"] for r in _snap.get("results", [])}
        except Exception:
            pass
static_dir = Path(__file__).resolve().parents[2] / "web"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


class SearchIntent(BaseModel):
    keywords: str = Field(default="", max_length=500)
    category: str = Field(default="", max_length=100)
    sources: list[str] | None = Field(default=None, max_length=10)
    hard: dict = {}
    blacklist: list[dict] = Field(default=[], max_length=50)
    whitelist: list[dict] = Field(default=[], max_length=50)
    required: list[dict] = Field(default=[], max_length=50)  # must-contain (AND): every rule must match
    risk: dict = {}
    ranking: dict | None = None
    enrich: bool = True
    enrich_top_n: int = Field(default=150, ge=0, le=1000)  # deep OCR/bench for top-N only
    limit: int | None = Field(default=None, ge=1, le=100000)  # None = unlimited
    max_pages: int | None = Field(default=None, ge=1, le=50)  # per-source page cap; empty = walk to exhaustion
    watch: bool = False
    poll_interval_s: int = Field(default=1800, ge=60, le=604800)
    notify_on: list[str] = ["new_top", "price_drop"]
    notify_rules: list[dict] = Field(default=[], max_length=20)  # e.g. {"kind":"price_drop","min_drop_pct":15},{"kind":"new_match","max_risk":0.2}
    max_distance_km: float | None = Field(default=None, ge=0, le=20000)
    require_pickup: bool = False
    require_shipping: bool = False


_ASSET_VER: dict[str, str] = {}


def _asset(name: str) -> str:
    """Cache-busted static URL: /static/app.js?v=<sha8>."""
    if name not in _ASSET_VER:
        import hashlib as _h
        p = Path(__file__).resolve().parents[2] / "web" / name
        _ASSET_VER[name] = _h.sha256(p.read_bytes()).hexdigest()[:8] if p.exists() else "0"
    return f"/static/{name}?v={_ASSET_VER[name]}"


def _page(name: str, fallback: str) -> HTMLResponse:
    p = Path(__file__).resolve().parents[2] / "web" / name
    if not p.exists():
        return HTMLResponse(fallback)
    html = p.read_text()
    for js in ("app.js", "admin.js"):
        html = html.replace(f"/static/{js}", _asset(js))
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


@app.get("/", response_class=HTMLResponse)
def index():
    return _page("index.html", "<h1>deal-radar up. See /docs</h1>")


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
    return _page("admin.html", "<h1>admin missing</h1>")


@app.get("/auth/status")
def auth_status(request: Request):
    return {"login_required": bool(LOGIN_PASSWORD), "logged_in": _logged_in(request)}


@app.post("/login")
async def login(request: Request):
    """Simple password login (OTP/users later). Sets HttpOnly session cookie."""
    if not LOGIN_PASSWORD:
        return JSONResponse({"ok": True, "note": "no password configured"})
    ip = request.client.host if request.client else "?"
    now = _t.time()
    lst = [t for t in _login_hits.get(ip, []) if now - t < 60]
    if len(lst) >= 5:
        return JSONResponse({"ok": False, "error": "too many attempts, wait a minute"},
                            status_code=429)
    lst.append(now)
    _login_hits[ip] = lst
    ctype = request.headers.get("content-type", "")
    if "application/json" in ctype:
        body = await request.json()
        pw = str(body.get("password", ""))
        wants_json = True
    else:
        form = await request.form()
        pw = str(form.get("password", ""))
        wants_json = False
    if not _hmac.compare_digest(pw, LOGIN_PASSWORD):
        if wants_json:
            return JSONResponse({"ok": False, "error": "wrong password"}, status_code=401)
        return _login_page("wrong password")
    import secrets as _sec
    _prune_sessions()
    tok = _sec.token_urlsafe(32)
    SESSIONS[tok] = now + SESSION_TTL
    if wants_json:
        resp: Response = JSONResponse({"ok": True})
    else:
        resp = RedirectResponse("/", status_code=303)
    resp.set_cookie("dr_session", tok, httponly=True, samesite="lax", max_age=SESSION_TTL,
                    secure=request.url.scheme == "https")
    return resp


@app.post("/logout")
def logout(request: Request):
    SESSIONS.pop(request.cookies.get("dr_session", ""), None)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("dr_session")
    return resp


class NLQuery(BaseModel):
    text: str = Field(max_length=2000)
    category: str = Field(default="", max_length=100)
    enrich_top_n: int = Field(default=150, ge=0, le=1000)
    sources: list[str] | None = Field(default=None, max_length=10)
    watch: bool = False
    poll_interval_s: int = Field(default=1800, ge=60, le=604800)
    limit: int | None = Field(default=None, ge=1, le=100000)  # None = unlimited
    max_pages: int | None = Field(default=None, ge=1, le=50)
    ocr: bool = True
    benchmarks: bool = True
    vision: bool = True
    details: bool = True


@app.post("/searches/nl")
async def create_nl_search(q: NLQuery):
    from deal_radar.decision import nl_to_intent
    parsed = await nl_to_intent(q.text)
    if (q.category or "").strip():
        parsed["category"] = q.category.strip().lower()
        parsed["keywords"] = ""
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
                        "enrich": True, "enrich_top_n": q.enrich_top_n, "max_pages": q.max_pages, "ocr": q.ocr, "benchmarks": q.benchmarks,
                        "vision": q.vision, "details": q.details,
                        "limit": None if q.limit is None else max(6, q.limit // max(1, len(queries))),
                        "watch": False, "poll_interval_s": q.poll_interval_s,
                        "notify_on": ["new_top", "price_drop"]})
    base = {"keywords": parsed.get("keywords", q.text), "category": parsed.get("category", ""),
            "sources": q.sources or default_sources(), "hard": {"min_match": 0.2, **(parsed.get("hard", {}) or {})},
            "blacklist": parsed.get("blacklist", []), "whitelist": [], "risk": {},
            "ranking": None, "attributes": parsed.get("attributes", {}),
            "models": parsed.get("models", []) or [],
            "required": parsed.get("required", []),
            "enrich": True, "enrich_top_n": q.enrich_top_n, "max_pages": q.max_pages, "ocr": q.ocr, "benchmarks": q.benchmarks,
            "vision": q.vision, "details": q.details,
            "limit": q.limit, "watch": q.watch,
            "poll_interval_s": q.poll_interval_s, "notify_on": ["new_top", "price_drop"]}
    return await _start_job(intents, {"parsed": parsed, "base": base, "subqueries": queries,
                                      "limit": q.limit, "watch": q.watch})


def _merge_outs(outs: list[dict], limit: int | None) -> dict:
    import statistics as _st
    seen: set[str] = set()
    merged: list[dict] = []
    flagged: list[dict] = []
    events: list[dict] = []
    errors: dict = {}
    filt = 0
    fetched: dict[str, int] = {}
    for o in outs:
        filt += o.get("filtered_out", 0)
        for src, n in (o.get("driver_fetched") or {}).items():
            fetched[src] = fetched.get(src, 0) + n
        events.extend(o.get("events", []))
        errors.update(o.get("driver_errors", {}))
        for r in o.get("results", []):
            lid = r["listing"]["id"]
            if lid not in seen:
                seen.add(lid)
                merged.append(r)
        for r in o.get("filtered", []):
            lid = r["listing"]["id"]
            if lid not in seen and len(flagged) < 5000:
                seen.add(lid)
                flagged.append(r)
    stopped = any(o.get("stopped") for o in outs)
    merged.sort(key=lambda r: r.get("final_score", 0), reverse=True)
    if limit:
        merged = merged[:limit]
    _mp = sorted(r["listing"]["price"] for r in merged if r["listing"].get("price") is not None)
    return {"results": merged, "filtered": flagged, "events": events, "driver_errors": errors,
            "driver_fetched": fetched, "stopped": stopped,
            "filtered_out": filt, "median": _st.median(_mp) if len(_mp) >= 3 else None}


JOBS: dict[str, dict] = {}


async def _start_job(intents: list[dict], meta: dict) -> dict:
    sid = f"s_{int(time.time() * 1000)}"
    base = meta.get("base", intents[0] if intents else {})
    JOBS[sid] = {"status": "running", "done": 0, "total": len(intents),
                 "intent": base, "control": "run", "detail": "queued",
                 "parsed": meta.get("parsed"), "subqueries": meta.get("subqueries", [])}
    try:
        store.job_upsert(sid, "running", 0, len(intents), base)
    except Exception:
        pass
    asyncio.create_task(_run_job(sid, intents, meta))
    return {"id": sid, "status": "running", "total": len(intents)}


_WATCH_KINDS = {"description": "desc_change", "images": "image_change",
                "title": "title_change", "seller": "seller_change"}


async def _notify_watch_changes(intent: dict, merged: dict) -> None:
    """Extra watch triggers beyond new_top/price_drop: desc/image/title/seller edits."""
    from deal_radar.notify_rules import rules_ok as _rules_ok
    want = set(intent.get("notify_on", []))
    if not (want & set(_WATCH_KINDS.values())):
        return
    for ev in merged.get("events", []):
        kind = _WATCH_KINDS.get(ev.get("kind", ""))
        if not kind or kind not in want:
            continue
        try:
            if not _rules_ok(intent.get("notify_rules", []), kind, ev=ev):
                continue
        except Exception:
            pass
        try:
            await notifier.send(
                f"{kind}: {(ev.get('title') or '')[:60]}",
                f"{ev.get('kind')} changed: {str(ev.get('old'))[:80]} → {str(ev.get('new'))[:80]}\n{ev.get('url', '')}",
                {"url": ev.get("url", "")})
        except Exception:
            pass


async def _run_job(sid: str, intents: list[dict], meta: dict) -> None:
    try:
        outs = []
        for i, data in enumerate(intents):
            _pt0 = time.time()
            while JOBS[sid].get("control") == "pause":
                if time.time() - _pt0 > 6 * 3600:  # abandoned pause auto-releases
                    JOBS[sid]["control"] = "stop"
                    break
                JOBS[sid]["detail"] = f"paused at sub-search {i + 1}/{len(intents)}"
                await asyncio.sleep(2)
                if JOBS[sid].get("control") == "stop":
                    break
            if JOBS[sid].get("control") == "stop":
                merged = _merge_outs(outs, meta.get("limit", None))
                merged["stopped"] = True
                JOBS[sid].update({"status": "stopped", "done": i, "result": merged,
                                  "detail": f"stopped after {i}/{len(intents)} sub-searches"})
                try:
                    store.job_upsert(sid, "stopped", i, len(intents),
                                     summary=f"{len(merged['results'])} partial results")
                except Exception:
                    pass
                return
            JOBS[sid]["done"] = i
            JOBS[sid]["detail"] = f"sub-search {i + 1}/{len(intents)}: {str(data.get('keywords', ''))[:60]}"
            try:
                store.job_upsert(sid, "running", i, len(intents))
            except Exception:
                pass
            data["_sid"] = sid
            try:
                outs.append(await _run_cached(data, force=True))
            finally:
                data.pop("_sid", None)
            # progressive partials: UI renders these while the job continues
            try:
                part = _merge_outs(outs, meta.get("limit", None))
                JOBS[sid]["partial"] = {"results": part["results"][:200],
                                        "filtered": part.get("filtered", [])[:100],
                                        "n_results": len(part["results"]),
                                        "n_filtered": len(part.get("filtered", []))}
            except Exception:
                pass
        JOBS[sid]["done"] = len(intents)
        try:
            from deal_radar import orchestrator as _orc2
            _orc2._STOP.discard(sid)
            _orc2._PAUSE.discard(sid)
        except Exception:
            pass
        merged = _merge_outs(outs, meta.get("limit", None))
        if any(o.get("stopped") for o in outs):
            merged["stopped"] = True
        base = meta.get("base", intents[0] if intents else {})
        SEARCHES[sid] = base
        store.save_search(sid, base, len(merged["results"]))
        try:
            _t0snap = time.time()
            await asyncio.to_thread(store.save_snapshot, sid, merged)
            metrics.observe_latency("snapshot_save", time.time() - _t0snap)
        except Exception:
            pass
        merged["flags"] = {k: bool(base.get(k, True)) for k in
                           ("enrich", "ocr", "benchmarks", "vision", "details")}
        if base.get("watch"):
            await _notify_watch_changes(base, merged)
        LAST_RUN[sid] = time.time()
        SEEN_IDS[sid] = {r["listing"]["id"] for r in merged["results"]}
        store.save_results(sid, merged["results"])
        try:
            store.job_upsert(sid, "done", len(intents), len(intents),
                             summary=f"{len(merged['results'])} results")
        except Exception:
            pass
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
        try:
            from deal_radar import orchestrator as _orc3
            _orc3._STOP.discard(sid)
            _orc3._PAUSE.discard(sid)
            _orc3._PAUSE_SINCE.pop(sid, None)
            store.job_upsert(sid, "error", JOBS[sid].get("done", 0),
                             len(intents), summary=f"{type(e).__name__}: {e}"[:200])
        except Exception:
            pass


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
    cats = [c.strip().lower() for c in str(data.get("category", "") or "").split(",") if c.strip()][:4]
    if len(cats) > 1 and not [p for p in (data.get("keywords", "") or "").split(";") if p.strip()][1:]:
        lim = data.get("limit")
        intents = [{**data, "category": c,
                    "limit": None if lim is None else max(6, lim // len(cats))} for c in cats]
        return await _start_job(intents, {"base": {**data, "watch": data.get("watch", False)},
                                          "subqueries": [f"cat:{c}" for c in cats],
                                          "limit": data.get("limit"), "watch": data.get("watch", False),
                                          "notify_done": True})
    # multi-query: "rtx 4080; rtx 4070 ti super" -> parallel sub-searches, merged
    # (cartesian with categories when both given, total fan-out capped at 6)
    parts = [p.strip() for p in (data.get("keywords", "") or "").split(";") if p.strip()]
    if len(parts) > 1:
        combo = [(p, c) for p in parts[:6] for c in (cats or [""] )][:6]
        lim = data.get("limit")
        intents = [{**data, "keywords": p, "category": c, "watch": False,
                    "limit": None if lim is None else max(6, lim // max(1, len(combo)))}
                   for p, c in combo]
        return await _start_job(intents, {"base": {**data, "watch": data.get("watch", False)},
                                          "subqueries": parts[:6], "limit": data.get("limit", 20),
                                          "watch": data.get("watch", False), "notify_done": True})
    return await _start_job([data], {"base": data, "limit": data.get("limit", 20),
                                     "watch": data.get("watch", False), "notify_done": True})


class WatchClone(BaseModel):
    poll_interval_s: int = Field(default=1800, ge=60, le=604800)
    notify_on: list[str] = ["new_top", "price_drop"]
    notify_rules: list[dict] = Field(default=[], max_length=20)


@app.post("/searches/{sid}/watch")
async def watch_clone(sid: str, w: WatchClone):
    from copy import deepcopy
    intent = SEARCHES.get(sid)
    if intent is None:
        try:
            row = store.db.execute("SELECT intent FROM searches WHERE id=?", (sid,)).fetchone()
            import json as _j
            intent = _j.loads(row[0]) if row else None
        except Exception:
            intent = None
    if not intent:
        return JSONResponse({"error": "unknown search id"}, status_code=404)
    data = deepcopy(intent)
    data["watch"] = True
    data["poll_interval_s"] = w.poll_interval_s
    data["notify_on"] = w.notify_on
    data["notify_rules"] = w.notify_rules
    return await _start_job([data], {"base": data, "limit": data.get("limit", 20),
                                     "watch": True, "notify_done": True})


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
        return JSONResponse({"error": "unknown search id"}, status_code=404)
    from copy import deepcopy
    return await _start_job([deepcopy(intent)], {"base": deepcopy(intent), "limit": intent.get("limit", 20),
                                                "watch": intent.get("watch", False), "notify_done": True})


@app.get("/searches/{sid}")
async def get_search(sid: str):
    job = JOBS.get(sid)
    if job is not None:
        if job["status"] == "running":
            from deal_radar import orchestrator as _orc
            _paused = sid in _orc._PAUSE
            out = {"id": sid, "status": "running", "done": job["done"], "total": job["total"],
                   "detail": "paused — resume to continue" if _paused else job.get("detail", ""),
                   "paused": _paused, "control": job.get("control", "run")}
            if job.get("partial"):
                out["partial"] = job["partial"]
            return out
        if job["status"] == "stopped":
            out = dict(job.get("result", {}))
            return {"id": sid, "status": "stopped", **out}
        if job["status"] == "error":
            return {"id": sid, "status": "error", "error": job.get("error")}
        out = job.get("result", {})
        return {"id": sid, "status": "done", "parsed": job.get("parsed"),
                "subqueries": job.get("subqueries", []), **out}
    try:
        row = store.db.execute("SELECT status, intent FROM jobs WHERE id=?", (sid,)).fetchone()
    except Exception:
        row = None
    if row and row[0] == "running":
        return {"id": sid, "status": "running", "adopted": True,
                "done": 0, "total": 1, "note": "still running (or interrupted by restart)"}
    intent = SEARCHES.get(sid)
    if not intent:
        return JSONResponse({"error": "unknown search id"}, status_code=404)
    snap = store.load_snapshot(sid)
    if not snap:
        # legacy rows (pre-snapshot era): reconstruct viewable cards from saved rows
        recs: list[dict] = []
        try:
            rows = store.db.execute(
                "SELECT listing_id, title, price, currency, source, url, image, score "
                "FROM search_results WHERE search_id=? ORDER BY rank LIMIT 500", (sid,)).fetchall()
            for lid, title, price, cur, src, url, img, score in rows:
                recs.append({"listing": {"id": lid, "source": src, "url": url, "title": title,
                                         "price": price, "currency": cur,
                                         "images": [img] if img else []},
                             "match_score": 0.5,
                             "deal_dna": {"match": 0.5, "value": 0.5, "risk": 0.0,
                                          "completeness": 0.5, "condition": 0.5,
                                          "confidence": 0.0, "total_cost": price or 0.0},
                             "risk": {"score": 0.0, "confidence": 0.0, "severity": "low",
                                      "reasons": [], "counter_evidence": []},
                             "enrichments": [], "value_score": 0.5, "final_score": score if score is not None else 0.5,
                             "lane": "review",
                             "why": ["reconstructed from saved rows (pre-snapshot search) — re-run for full analysis"]})
        except Exception:
            recs = []
        if recs:
            return {"id": sid, "status": "done", "cached": True, "reconstructed": True,
                    "intent": intent, "results": recs, "filtered": []}
        return {"id": sid, "status": "empty",
                "error": "no saved snapshot for this search — press re-run for fresh results",
                "intent": intent, "results": [], "filtered": []}
    return {"id": sid, "status": "done", "cached": True, "snapshot": True,
            "intent": intent, **snap}


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


@app.post("/searches/{sid}/stop")
def stop_search(sid: str):
    job = JOBS.get(sid)
    if job is None:
        return JSONResponse({"error": "unknown search id"}, status_code=404)
    if job.get("status") != "running":
        return JSONResponse({"error": "job is not running"}, status_code=409)
    job["control"] = "stop"
    try:
        from deal_radar import orchestrator as _orc
        _orc._STOP.add(sid)
        _orc._PAUSE.discard(sid)
    except Exception:
        pass
    return {"ok": True, "id": sid}


@app.post("/searches/{sid}/pause")
def pause_search(sid: str):
    job = JOBS.get(sid)
    if job is None:
        return JSONResponse({"error": "unknown search id"}, status_code=404)
    if job.get("status") != "running":
        return JSONResponse({"error": "job is not running"}, status_code=409)
    job["control"] = "pause"
    try:
        from deal_radar import orchestrator as _orc
        _orc._PAUSE.add(sid)
    except Exception:
        pass
    return {"ok": True, "id": sid}


@app.post("/searches/{sid}/resume")
def resume_search(sid: str):
    job = JOBS.get(sid)
    if job is None:
        return JSONResponse({"error": "unknown search id"}, status_code=404)
    if job.get("status") != "running":
        return JSONResponse({"error": "job is not running"}, status_code=409)
    job["control"] = "run"
    try:
        from deal_radar import orchestrator as _orc
        _orc._PAUSE.discard(sid)
    except Exception:
        pass
    return {"ok": True, "id": sid}


@app.delete("/searches/{sid}")
def delete_search(sid: str):
    SEARCHES.pop(sid, None)
    SEEN_IDS.pop(sid, None)
    LAST_RUN.pop(sid, None)
    store.delete_search(sid)
    return {"ok": True}


class LabRequest(BaseModel):
    kind: str = Field(default="enricher", pattern="^(enricher|driver)$")
    instruction: str = Field(default="", max_length=4000)
    publish: bool = False


LAB_JOBS: dict[str, dict] = {}


async def _lab_run(jid: str, kind: str, instruction: str, followup: str,
                   prior_code: str, prior_error: str, publish: bool) -> None:
    from deal_radar import ailab
    job = LAB_JOBS[jid]
    def prog(stage: str, msg: str):
        job["stage"] = stage
        job["log"].append({"ts": time.time(), "stage": stage, "msg": msg})
    try:
        out = await ailab.generate(kind, instruction, followup, prior_code, prior_error, prog)
        job["result"] = out
        if out.get("ok") and publish:
            out["pr"] = await lab_publish(out)
        job["status"] = "done" if out.get("ok") else "failed"
    except Exception as e:
        job["status"] = "error"
        job["result"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}


class FactOverride(BaseModel):
    field: str = Field(default="cpu", pattern="^[a-z][a-z0-9_]{0,29}$")
    value: str = Field(default="", max_length=200)


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
    id: str = Field(default="", pattern="^[a-z0-9][a-z0-9-]{0,40}$")


@app.delete("/marketplace/{did}")
def marketplace_uninstall(did: str):
    from deal_radar.registry import uninstall
    out = uninstall(did)
    if not out.get("ok"):
        return JSONResponse(out, status_code=404)
    registry.unregister(did)
    return out


@app.post("/marketplace/install")
def marketplace_install(req: InstallRequest):
    """Single-click install from the marketplace index (checksummed + contract-checked)."""
    from deal_radar.registry import load_index
    try:
        idx = load_index()
    except Exception:
        idx = {"drivers": []}
    if not idx.get("drivers"):
        import json as _j
        p = Path(__file__).resolve().parents[2] / "marketplace" / "index.json"
        idx = _j.loads(p.read_text()) if p.exists() else {"drivers": []}
    entry = next((d for d in idx.get("drivers", []) if d["id"] == req.id), None)
    if not entry:
        return JSONResponse({"ok": False, "error": f"unknown marketplace id: {req.id}"}, status_code=404)
    if entry.get("source") == "builtin":
        return {"ok": True, "installed": req.id, "note": "built in — enable per search"}
    from deal_radar.registry import install, load_driver_module
    out = install(entry)
    if out.get("ok"):
        try:
            mod = load_driver_module(entry["id"])
            drivers = [v for v in vars(mod).values() if isinstance(v, type)
                       and getattr(v, "manifest", None) is not None
                       and v.__name__.endswith("Driver")]
            if drivers:
                registry.register(drivers[0]())
        except Exception as e:
            return {"ok": True, "installed": entry["id"],
                    "note": f"installed but live load failed ({e}); restarts to activate"}
    return out


@app.get("/notifications/status")
def notifications_status():
    chans = []
    if os.getenv("SIGNAL_NUMBER"):
        chans.append({"type": "signal", "configured": True})
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


class LabFollow(BaseModel):
    job_id: str = ""
    followup: str = Field(default="", max_length=4000)
    publish: bool = False


def _lab_start(kind: str, instruction: str, followup: str = "", prior_code: str = "",
               prior_error: str = "", publish: bool = False) -> dict:
    jid = f"lab_{int(time.time() * 1000)}"
    LAB_JOBS[jid] = {"status": "running", "stage": "queued", "log": [],
                     "kind": kind, "instruction": instruction}
    asyncio.create_task(_lab_run(jid, kind, instruction, followup, prior_code,
                                 prior_error, publish))
    return {"id": jid, "status": "running"}


@app.post("/lab/build")
async def lab_build(req: LabRequest):
    if not os.getenv("LAB_ENABLED"):
        return JSONResponse({"ok": False, "error": "LAB_ENABLED=0 (code-writing disabled)"}, status_code=400)
    return _lab_start(req.kind, req.instruction, publish=req.publish)


@app.get("/lab/build/{jid}")
def lab_job(jid: str):
    job = LAB_JOBS.get(jid)
    if not job:
        return JSONResponse({"error": "unknown lab job"}, status_code=404)
    return job


@app.post("/lab/follow")
async def lab_follow(req: LabFollow):
    """User steps in: new instruction applied on top of the previous attempt's code."""
    if not os.getenv("LAB_ENABLED"):
        return JSONResponse({"ok": False, "error": "LAB_ENABLED=0 (code-writing disabled)"}, status_code=400)
    if not req.job_id or req.job_id not in LAB_JOBS:
        return JSONResponse({"error": "unknown lab job"}, status_code=404)
    if not req.followup.strip():
        return JSONResponse({"error": "followup text required"}, status_code=400)
    prev = LAB_JOBS[req.job_id]
    res = prev.get("result", {}) if isinstance(prev, dict) else {}
    code = res.get("code", "")
    if not code and res.get("path"):
        try:
            code = (await asyncio.to_thread(Path(res["path"]).read_text))[:6000]
        except Exception:
            code = ""
    return _lab_start(prev.get("kind", "enricher"), prev.get("instruction", ""),
                      req.followup, code, res.get("error", ""), req.publish)


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
        return JSONResponse({"error": "unknown search id"}, status_code=404)
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
    return {"items": items, "limit": max(1, min(limit, 200)), "offset": max(0, offset)}

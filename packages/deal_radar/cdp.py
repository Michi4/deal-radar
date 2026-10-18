"""Generic Chrome DevTools Protocol (CDP) session transport.

Why this exists: a growing set of marketplaces render results only in a real
browser (JS app-shell + anti-bot) and refuse anonymous HTTP (AliExpress, 1688,
eBay-at, ...). Those sites are reachable through the *user's own* Chrome — the
same "chrome debug browser" path the owner proposed. Nothing here evades a
captcha or forges identity: it drives a browser the user launched, with the
user's own session, one polite navigation per search.

Usage (server side): launch Chrome once with a debug port
    google-chrome --remote-debugging-port=9222 --user-data-dir=<profile>
log in to the target site in that window, then point a driver's transport at it:

    TRANSPORTS_JSON = {"aliexpress": {"type": "cdp", "url": "http://<host>:9222"}}

In Docker the app reaches the host browser via ``host.docker.internal:9222``.
``CDP_URL`` (Secrets UI) is the default endpoint for every driver that does not
carry its own transport config.

The transport exposes ``get(url)`` like every other TransportProvider, so a
session driver is written exactly like a normal HTTP driver and its parser is a
pure function of the returned HTML (trivially unit-testable on a saved capture).
"""
from __future__ import annotations

import asyncio
import json
import time
import urllib.parse
import urllib.request
from typing import Any

import httpx

from .driver_sdk import TransportProvider

DEFAULT_CDP_URL = "http://localhost:9222"
_NAV_LOCKS: dict[str, asyncio.Lock] = {}


def _nav_lock(cdp_url: str) -> asyncio.Lock:
    """One tab per endpoint means one navigation at a time — parallel hunts on
    the same browser would otherwise scrape each other's pages."""
    lock = _NAV_LOCKS.get(cdp_url)
    if lock is None:
        lock = asyncio.Lock()
        _NAV_LOCKS[cdp_url] = lock
    return lock


def cdp_targets(cdp_base: str, timeout: float = 15.0) -> list[dict]:
    with urllib.request.urlopen(cdp_base.rstrip("/") + "/json/list", timeout=timeout) as r:
        return json.loads(r.read().decode())


def cdp_reachable(cdp_base: str, timeout: float = 5.0) -> bool:
    try:
        with urllib.request.urlopen(cdp_base.rstrip("/") + "/json/version", timeout=timeout):
            return True
    except Exception:
        return False


def cdp_rpc(cdp_base: str, method: str, params: dict | None = None,
            target_id: str | None = None, timeout: float = 40.0) -> dict:
    """Minimal CDP request/response over a fresh websocket. Imported lazily so
    unit tests never need the websockets stack."""
    targets = cdp_targets(cdp_base)
    page = next((t for t in targets
                 if t.get("type") == "page" and (target_id is None or t["id"] == target_id)), None)
    if page is None:
        pages = [t for t in targets if t.get("type") == "page"]
        if not pages:
            raise RuntimeError("no open tab on the debug browser — launch Chrome with "
                               "--remote-debugging-port and open one tab")
        page = pages[0]

    async def _go() -> dict:
        from websockets.asyncio.client import connect
        async with connect(page["webSocketDebuggerUrl"], max_size=96 * 1024 * 1024) as ws:
            await ws.send(json.dumps({"id": 1, "method": method, "params": params or {}}))
            while True:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout))
                if m.get("id") == 1:
                    if "error" in m:
                        raise RuntimeError(f"CDP {method}: {m['error'].get('message', m['error'])}")
                    return m.get("result", {})

    return asyncio.run(_go())


class CdpTransport(TransportProvider):
    """Renders each URL in a real (headed) Chrome via CDP and returns the DOM.

    Per request: one navigation, a readiness poll, a short settle wait for the
    client-side hydration, then ``documentElement.outerHTML``. Politeness lives
    in the drivers (their rate limits / pagination caps).
    """

    def __init__(self, cdp_url: str = DEFAULT_CDP_URL, timeout: float = 90.0,
                 settle: float = 5.0, ready_selector: str = "", min_bytes: int = 8000):
        self.cdp_url = (cdp_url or DEFAULT_CDP_URL).rstrip("/")
        self.timeout = timeout
        self.settle = settle
        self.ready_selector = ready_selector
        self.min_bytes = min_bytes
        self.last_title = ""

    def _readiness_expr(self) -> str:
        sel = json.dumps(self.ready_selector)
        return (f"(function(){{return document.readyState + ' ### ' + "
                f"document.documentElement.outerHTML.length + ' ### ' + "
                f"({sel} ? document.querySelectorAll({sel}).length : 1);}})()")

    def _page_html(self, url: str) -> str:
        if not cdp_reachable(self.cdp_url):
            raise RuntimeError(f"debug browser unreachable at {self.cdp_url} — launch Chrome "
                               f"with --remote-debugging-port (see BLOCKERS.md)")
        cdp_rpc(self.cdp_url, "Page.navigate", {"url": url}, timeout=30)
        deadline = time.time() + self.timeout
        # readiness: document complete + enough bytes (selectors may be lazy)
        while time.time() < deadline:
            time.sleep(2)
            try:
                r = cdp_rpc(self.cdp_url, "Runtime.evaluate",
                            {"expression": self._readiness_expr(), "returnByValue": True}, timeout=30)
            except Exception:
                continue
            state = (r.get("result") or {}).get("value", "") or ""
            parts = state.split(" ### ")
            if parts[0] == "complete" and parts[1].isdigit() and int(parts[1]) >= self.min_bytes:
                break
        if self.settle:
            time.sleep(self.settle)  # let client-side rendering finish
        r = cdp_rpc(self.cdp_url, "Runtime.evaluate",
                    {"expression": "document.documentElement.outerHTML", "returnByValue": True},
                    timeout=60)
        html = (r.get("result") or {}).get("value", "") or ""
        if len(html) < self.min_bytes:
            raise RuntimeError(f"debug browser returned only {len(html)} bytes for {url} "
                               f"(page blocked, still loading, or session expired)")
        title = ""
        try:
            t = cdp_rpc(self.cdp_url, "Runtime.evaluate",
                        {"expression": "document.title", "returnByValue": True}, timeout=20)
            title = (t.get("result") or {}).get("value", "") or ""
        except Exception:
            title = ""
        self.last_title = title
        return html

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        async with _nav_lock(self.cdp_url):
            html = await asyncio.to_thread(self._page_html, url)
        body = html.encode("utf-8", "replace")
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"},
                              content=body, request=httpx.Request("GET", url))


def aliexpress_search_url(keywords: str, page: int = 1) -> str:
    """AliExpress search entry point that Chrome redirects to the localized
    /w/wholesale-<slug>.html page. ``page`` is 1-based."""
    q = urllib.parse.quote_plus((keywords or "").strip())
    url = f"https://www.aliexpress.com/wholesale?SearchText={q}"
    if page and page > 1:
        url += f"&page={page}"
    return url

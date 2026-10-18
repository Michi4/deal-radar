"""AliExpress driver — new-product marketplace via the user's own debug browser.

Access path (researched live 2026-10-18): AliExpress serves a 301 redirect stub
to anonymous HTTP (Tengine `x-rule-name: AE_GLOBAL_UNLOGIN`) and its search page
is a JS app-shell, so plain httpx/curl gets nothing. A real headed Chrome
(CDP transport, ``packages/deal_radar/cdp.py``) renders the full result grid:
``a.search-card-item`` cards with title, price, image and sold-count. That is
the "chrome debug browser" path the owner proposed — a browser the operator runs
and logs into, never captcha evasion.

Setup: launch Chrome once with ``--remote-debugging-port=9222`` and set
``CDP_URL`` in Admin → Secrets (or a per-driver ``TRANSPORTS_JSON`` entry:
``{"aliexpress": {"type": "cdp", "url": "http://host.docker.internal:9222"}}``).
Without it the driver raises a clean configured-error and the orchestrator marks
the source degraded — no fake listings, no scraping fallback.
"""
from __future__ import annotations

import asyncio
import html as _html
import re

from deal_radar.cdp import CdpTransport, aliexpress_search_url
from deal_radar.contracts import CanonicalListing, Seller
from deal_radar.driver_sdk import DriverManifest, MarketplaceDriver, SearchQuery

DEFAULT_PAGES = 3  # polite default; the aggregator can request more via max_pages

_CARD_RE = re.compile(r'<a class="[^"]*search-card-item[^"]*".*?</a>', re.DOTALL)
_ID_RE = re.compile(r"/item/(\d+)\.html")
_TITLE_H3_RE = re.compile(r'us--titleText--[^"]*"[^>]*>([^<]{3,300})<')
_TITLE_ARIA_RE = re.compile(r'class="us--title--[^"]*"[^>]*aria-label="([^"]{3,300})"')
_PRICE_RE = re.compile(r'us--price--[^"]*"[^>]*aria-label="([^"]{1,40})"')
_IMG_RE = re.compile(r'<img[^>]+src="([^"]+)"')
_SOLD_RE = re.compile(r"us--trade--[^\"]*\">([^<]{1,30})<")


def parse_price(raw: str) -> tuple[float | None, str]:
    """'€1,865.57' -> (1865.57, 'EUR'); '€135.74' -> (135.74, 'EUR');
    '1.865,57 €' -> (1865.57, 'EUR'); ranges take the first figure."""
    t = (raw or "").replace("\xa0", " ").strip()
    if not t:
        return None, ""
    cur = "EUR"
    if "$" in t or "US $" in t:
        cur = "USD"
    elif "£" in t:
        cur = "GBP"
    m = re.search(r"[\d.,]+", t)
    if not m:
        return None, cur
    num = m.group(0)
    if "," in num and "." in num:
        if num.rfind(",") > num.rfind("."):
            num = num.replace(".", "").replace(",", ".")
        else:
            num = num.replace(",", "")
    elif "," in num:
        num = num.replace(",", ".") if len(num.split(",")[-1]) <= 2 else num.replace(",", "")
    try:
        return float(num), cur
    except ValueError:
        return None, cur


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _abs_url(u: str) -> str:
    u = (u or "").strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return "https://www.aliexpress.com" + u
    return u


def parse_aliexpress_search(doc: str, limit: int = 60) -> list[dict]:
    """Pure parser for a saved AliExpress search page. Dedupes by item id."""
    out: list[dict] = []
    seen: set[str] = set()
    for card in _CARD_RE.findall(doc or ""):
        hm = re.search(r'href="([^"]+)"', card)
        if not hm:
            continue
        href = _html.unescape(hm.group(1))
        im = _ID_RE.search(href)
        if not im:
            continue
        iid = im.group(1)
        if iid in seen:
            continue
        tm = _TITLE_H3_RE.search(card) or _TITLE_ARIA_RE.search(card)
        title = _clean(tm.group(1)) if tm else ""
        if not title:
            continue
        pm = _PRICE_RE.search(card)
        price, currency = parse_price(_html.unescape(pm.group(1)) if pm else "")
        if price is None:
            continue
        imgs: list[str] = []
        for src in _IMG_RE.findall(card):
            u = _abs_url(_html.unescape(src))
            if u and u not in imgs and ("aliexpress-media" in u or "alicdn" in u):
                imgs.append(u)
        sm = _SOLD_RE.search(card)
        seen.add(iid)
        out.append({"id": iid, "title": title, "url": f"https://www.aliexpress.com/item/{iid}.html",
                    "price": price, "currency": currency or "EUR",
                    "images": imgs[:6], "sold": _clean(sm.group(1)) if sm else "",
                    "sponsored": "Werbeanzeige" in card,
                    "free_shipping": "kostenloser versand" in card.lower()})
        if len(out) >= limit:
            break
    return out


class AliexpressDriver(MarketplaceDriver):
    manifest = DriverManifest(id="aliexpress", version="0.1.0", display_name="AliExpress",
                              regions=["eu", "global"],
                              capabilities=["search", "images"],
                              access_mode="user_session_web",
                              automation_permission="unknown", rate_limit_rpm=6)

    def __init__(self, transport=None, cdp_url: str = ""):
        super().__init__(transport)
        self.cdp_url = cdp_url

    @staticmethod
    def configured() -> bool:
        import os
        return bool(os.getenv("CDP_URL"))

    def _session_ready(self) -> bool:
        if isinstance(self.transport, CdpTransport):
            return True
        return self.cdp_url.strip() != ""

    async def search(self, query: SearchQuery) -> list[CanonicalListing]:
        if not self._session_ready():
            raise RuntimeError("aliexpress needs a debug-browser session — set CDP_URL in "
                               "Admin → Secrets (or a TRANSPORTS_JSON cdp entry) and launch "
                               "Chrome with --remote-debugging-port=9222")
        pages = query.max_pages or DEFAULT_PAGES
        limit = query.limit or 60
        from deal_radar.cancel import pause_gate, should_stop
        out: list[CanonicalListing] = []
        seen: set[str] = set()
        for page in range(1, max(1, pages) + 1):
            if should_stop(query.sid):
                break
            if await pause_gate(query.sid):
                break
            url = aliexpress_search_url(query.keywords or "", page)
            try:
                resp = await self.transport.get(url, headers={"Accept": "text/html"})
            except Exception as e:
                if out:
                    break  # keep what we already have rather than fail the source
                raise RuntimeError(f"aliexpress session fetch failed: {e}") from e
            items = parse_aliexpress_search(resp.text, limit=limit)
            new = [it for it in items if it["id"] not in seen]
            if not new:
                break
            for it in new:
                seen.add(it["id"])
                if query.max_price and it["price"] > query.max_price:
                    continue
                if query.min_price and it["price"] < query.min_price:
                    continue
                out.append(CanonicalListing(
                    id=f"aliexpress:{it['id']}", source="aliexpress", native_id=it["id"],
                    url=it["url"], title=it["title"], description="",
                    price=it["price"], currency=it["currency"],
                    images=it["images"], seller=Seller(name="AliExpress seller"),
                    condition="new", shipping_available=it["free_shipping"],
                    attributes={"sold": it["sold"], "sponsored": it["sponsored"],
                                "free_shipping": it["free_shipping"]}))
                if len(out) >= limit:
                    return out
            await asyncio.sleep(1.0)  # politeness between pages
        return out

"""eBay session-web driver (headed-Chrome + user login + CDP).

Why this exists: eBay's bot wall 403s every anonymous stack (curl, curl_cffi,
headless shell — laptop AND cloud egress) and serves decoy cards to bare
headless sessions. A headed Chromium with the user's own logged-in profile
gets real search pages. Polite by construction: one navigation per search
(first results page, up to 120 cards), gentle waits, zero pagination hammering.

Setup (laptop with a display):
  1. chromium --user-data-dir=<profile> --remote-debugging-port=9222
  2. Log into ebay.at in that window once (profile persists the session).
  3. EBAY_CDP_URL=http://localhost:9222  (default)
Server use additionally needs EBAY_COOKIES_JSON (Cookie-Editor export) because
there is no display; headed runs under xvfb. Without either, search() raises
a clean configured-error and the orchestrator marks the source degraded.

ToS: personal, low-volume hobbyist use (<=1 req/s). Never hammer.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import urllib.parse
import urllib.request

from deal_radar.contracts import CanonicalListing, Seller
from deal_radar.driver_sdk import DriverManifest, MarketplaceDriver, SearchQuery

SEARCH_URL = "https://www.ebay.at/sch/i.html?_nkw={q}&_sop=15&_ipg=120"
JUNK_TITLES = {"", "Shop on eBay"}

_CDP_TIMEOUT = 90

_NAV_LOCK = None


def _nav_lock():
    """Single shared tab means one navigation at a time — parallel hunts
    would otherwise scrape each other's pages (wrong-query results)."""
    global _NAV_LOCK
    if _NAV_LOCK is None:
        import asyncio
        _NAV_LOCK = asyncio.Lock()
    return _NAV_LOCK


def _title_matches(html: str, keywords: str) -> bool:
    import re as _re
    m = _re.search(r"<title>([^<]{3,120})", html or "")
    if not m:
        return False
    toks = [t.lower() for t in _re.findall(r"[a-z0-9äöü]{4,}", (keywords or "").lower())]
    if not toks:
        return True
    title = m.group(1).lower()
    return any(t in title for t in toks)


def parse_price(raw: str) -> tuple[float | None, str]:
    """'EUR 49,00' -> (49.0, 'EUR'); ranges take the first figure."""
    t = (raw or "").replace("\xa0", " ").strip()
    m = re.search(r"(EUR|USD|GBP|CHF|US\s*\$|\$|£)\s*([\d.,]+)", t)
    if not m:
        m = re.search(r"([\d.,]+)\s*(EUR|USD|GBP|CHF)?", t)
        if not m:
            return None, ""
    cur = (m.group(1) if m.lastindex == 2 else (m.group(2) or "")).upper().replace("US $", "USD").replace("$", "USD").replace("£", "GBP").strip()
    num = m.group(2) if m.lastindex == 2 else m.group(1)
    num = num.strip()
    try:
        if "," in num:
            num = num.replace(".", "").replace(",", ".")
        return float(num), cur or "EUR"
    except ValueError:
        return None, cur or "EUR"


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def parse_ebay_search(html: str, limit: int = 60) -> list[dict]:
    """Pure parser for a saved eBay search page. Skips decoy/placeholder slots."""
    cards = re.split(r'<li class="s-card ', html)[1:]
    out: list[dict] = []
    seen: set[str] = set()
    for c in cards:
        mid = re.search(r'data-listingid="(\d+)"', c)
        if not mid or mid.group(1) in seen:
            continue
        iid = mid.group(1)
        tm = re.search(r'class="s-card__title"><span class="su-styled-text[^"]*">([^<]{4,200})</span>', c)
        title = _clean(tm.group(1)) if tm else ""
        if title in JUNK_TITLES:
            continue
        um = re.search(r'href="(https://www\.ebay\.at/itm/\d+)', c)
        url = um.group(1) if um else f"https://www.ebay.at/itm/{iid}"
        pm = re.search(r's-card__price">([^<]{2,80})</span>', c)
        price, currency = parse_price(pm.group(1) if pm else "")
        if not title or price is None:
            continue
        seen.add(iid)
        ship = 0.0
        sm = re.search(r"\+?\s*(EUR|USD|GBP|CHF)?\s*([\d.,]+)\s*Versand", c)
        if sm:
            p, _ = parse_price(sm.group(0))
            ship = p or 0.0
        free_ship = "Kostenloser Versand" in c
        seller = ""
        rating = ""
        sm2 = re.search(r's-card__attribute-row"><span class="su-styled-text primary large">([a-zA-Z0-9_.\-]{2,40}) </span><span class="su-styled-text primary large">(\d[\d.,]*K?%?\s*positiv\s*\(\d[\d.,]*K?\))', c)
        if sm2:
            seller, rating = sm2.group(1), _clean(sm2.group(2))
        sub = re.search(r's-card__subtitle"><span class="su-styled-text secondary default">([^<]{2,40}) \| </span><span class="su-styled-text secondary default">([^<]{2,40})</span>', c)
        condition = _clean(sub.group(1)) if sub else ""
        seller_kind = _clean(sub.group(2)) if sub else ""
        loc = ""
        lm = re.search(r"aus ([A-ZÄÖÜ][a-zäöüA-ZÄÖÜ ]{2,30})</", c)
        if lm:
            loc = lm.group(1).strip()
        img = re.search(r'<img[^>]+src="(https://i\.ebayimg\.com/[^"]+)"', c)
        out.append({"id": iid, "title": title, "url": url, "price": price,
                    "currency": currency or "EUR", "shipping": ship,
                    "free_shipping": free_ship, "seller": seller, "rating": rating,
                    "condition": condition, "seller_kind": seller_kind,
                    "location": loc,
                    "image": img.group(1) if img else "",
                    "auction": "Gebote" in c, "parts_only": "Nur Ersatzteile" in c,
                    "coupon": "mit Gutschein" in c,
                    "watchers": (_clean(w.group(1)) if (w := re.search(r"(\d+)\s*Beobachter", c)) else "")})
        if len(out) >= limit:
            break
    return out


def _cdp_targets(cdp_base: str) -> list[dict]:
    with urllib.request.urlopen(cdp_base + "/json/list", timeout=15) as r:
        return json.loads(r.read().decode())


def _cdp_rpc(cdp_base: str, target_id: str | None, method: str,
             params: dict | None = None, timeout: int = 30) -> dict:
    """Minimal CDP over websocket. Imported lazily so unit tests never need it."""
    import asyncio

    targets = _cdp_targets(cdp_base)
    page = next((t for t in targets
                 if t.get("type") == "page" and (target_id is None or t["id"] == target_id)), None)
    if page is None:
        pages = [t for t in targets if t.get("type") == "page"]
        if not pages:
            raise RuntimeError("no open Chrome tab on the debug browser — launch it first")
        page = pages[0]

    async def _go() -> dict:
        from websockets.asyncio.client import connect
        async with connect(page["webSocketDebuggerUrl"], max_size=32 * 1024 * 1024) as ws:
            rid = 1
            await ws.send(json.dumps({"id": rid, "method": method, "params": params or {}}))

            async def _wait() -> dict:
                while True:
                    m = json.loads(await asyncio.wait_for(ws.recv(), timeout))
                    if m.get("id") == rid:
                        if "error" in m:
                            raise RuntimeError(f"CDP {method}: {m['error'].get('message', m['error'])}")
                        return m.get("result", {})

            return await _wait()

    return asyncio.run(_go())


CARDS_JS = """(() => {
  const cards = [];
  document.querySelectorAll('li.s-card').forEach(li => {
    const t = li.querySelector('.s-card__title .su-styled-text, .s-card__title');
    const a = li.querySelector('a.s-card__link[href*="/itm/"], a[href*="ebay.at/itm/"]');
    const p = li.querySelector('.s-card__price');
    const title = t ? t.textContent.trim().replace(/\\s+/g,' ').slice(0,140) : '';
    const url = a ? a.href.split('?')[0] : '';
    if (!title || title === 'Shop on eBay' || !url.includes('/itm/') || url.includes('itm/123456')) return;
    const s = li.querySelector('.s-card__shipping, .s-card__shipment');
    if (p) cards.push({title, url, price: p.textContent.trim().replace(/\\s+/g,' ').slice(0,40),
      ship: s ? s.textContent.trim().replace(/\\s+/g,' ').slice(0,60) : ''});
  });
  return {n: cards.length, cards};
})()"""


class EbayWebDriver(MarketplaceDriver):
    manifest = DriverManifest(id="ebay-web", version="0.1.0", display_name="eBay (session)",
                              regions=["at", "de", "eu"], capabilities=["search", "images"],
                              access_mode="user_session_web", automation_permission="permitted",
                              rate_limit_rpm=6)

    def __init__(self, transport=None, cdp_url: str = "", cookies_json: str = ""):
        super().__init__(transport)
        import os
        self.cdp_url = (cdp_url or os.getenv("EBAY_CDP_URL", "http://localhost:9222")).rstrip("/")
        self.cookies_json = cookies_json or os.getenv("EBAY_COOKIES_JSON", "")

    @staticmethod
    def configured() -> bool:
        import os
        return bool(os.getenv("EBAY_CDP_URL") or os.getenv("EBAY_COOKIES_JSON"))

    def _page_html(self, url: str) -> str:
        try:
            with urllib.request.urlopen(self.cdp_url + "/json/version", timeout=10):
                pass
        except Exception as e:
            raise RuntimeError(f"eBay debug browser unreachable at {self.cdp_url} "
                               f"(launch headed Chrome with --remote-debugging-port first): {e}")
        _cdp_rpc(self.cdp_url, None, "Page.navigate", {"url": url})
        deadline = time.time() + _CDP_TIMEOUT
        while time.time() < deadline:
            time.sleep(7)
            r = _cdp_rpc(self.cdp_url, None, "Runtime.evaluate",
                         {"expression": "document.title + ' ### ' + document.querySelectorAll('li.s-card').length",
                          "returnByValue": True})
            state = (r.get("result") or {}).get("value", "")
            if "Ergebnisse" in state or re.search(r"###\s*[1-9]", state):
                break
        r = _cdp_rpc(self.cdp_url, None, "Runtime.evaluate",
                     {"expression": "document.documentElement.outerHTML", "returnByValue": True})
        html = (r.get("result") or {}).get("value", "")
        if len(html) < 50000 or "Error Page | eBay" in html[:5000]:
            raise RuntimeError("eBay served an error/block page — session may need refresh (log in again)")
        return html

    async def search(self, query: SearchQuery) -> list[CanonicalListing]:
        try:
            async with _nav_lock():
                html = await asyncio.to_thread(
                    self._page_html,
                    SEARCH_URL.format(q=urllib.parse.quote(query.keywords or "")))
                if not _title_matches(html, query.keywords or ""):
                    # another hunt owned the tab: re-navigate once, then accept
                    html = await asyncio.to_thread(
                        self._page_html,
                        SEARCH_URL.format(q=urllib.parse.quote(query.keywords or "")))
        except Exception as e:
            msg = str(e)
            if "eBay debug browser unreachable" in msg or "error/block page" in msg:
                raise
            raise RuntimeError(f"ebay-web hunt failed: {e}")
        items = parse_ebay_search(html, query.limit or 60)
        out: list[CanonicalListing] = []
        for it in items:
            if query.max_price and (it["price"] or 0) > query.max_price:
                continue
            if query.min_price and (it["price"] or 0) < query.min_price:
                continue
            cond = it["condition"] or ("parts-only" if it["parts_only"] else "")
            if "Ersatzteile" in cond or it["parts_only"]:
                cond = "parts-only"
            out.append(CanonicalListing(
                id=f"ebay-web:{it['id']}", source="ebay-web", native_id=it["id"],
                url=it["url"], title=it["title"], description="",
                price=it["price"], currency=it["currency"] or "EUR",
                images=[it["image"]] if it["image"] else [],
                seller=Seller(name=it["seller"] or "ebay seller"),
                location=it["location"], condition=cond,
                attributes={"shipping": it["shipping"], "free_shipping": it["free_shipping"],
                            "rating": it["rating"], "seller_kind": it["seller_kind"],
                            "auction": it["auction"], "coupon": it["coupon"],
                            "watchers": it["watchers"]}))
        return out

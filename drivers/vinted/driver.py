"""Vinted driver — public web SSR (permission: unknown; personal hobbyist use only).

Strategy: catalog search page is server-rendered with item cards
(data-testid product-item-id-*-overlay-link, price in img alt text incl. fees).
Sequential pages via catalog-pagination--next-page link.
"""
from __future__ import annotations

import re
from urllib.parse import quote_plus

from deal_radar.contracts import CanonicalListing
from deal_radar.driver_sdk import (
    DriverManifest,
    MarketplaceDriver,
    SearchQuery,
    eu_price,
)


def _unesc(s: str) -> str:
    return s.replace("&quot;", '"').replace("&amp;", "&").replace("&#x27;", "'").strip()


def parse_cards(html: str, limit: int = 30) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for m in re.finditer(
            r'<a[^>]+href="(/items/\d+[^"]*)"[^>]*data-testid="product-item-id-(\d+)--overlay-link"[^>]*title="([^"]{3,300})"',
            html):
        href, adid, title = m.group(1), m.group(2), _unesc(m.group(3))
        if adid in seen:
            continue
        seen.add(adid)
        url = href if href.startswith("http") else f"https://www.vinted.de{href.split('?')[0]}"
        # price: look for the card's img alt "...., 140.00 €, 147.70 €" (price, +protection total)
        block = html[max(0, m.start() - 1500):m.start()]
        prices = re.findall(r"([\d][\d\.\s,]*)\s*€", block[-800:])
        price = eu_price(prices[0]) if prices else None
        img = re.search(r'<img[^>]+src="(https://images\d*\.vinted\.net/[^"]+)"[^>]*>$', block[-800:]) or \
            re.search(r'src="(https://images\d*\.vinted\.net/[^"]+)"', block[-800:])
        out.append({"id": adid, "title": title, "url": url, "price": price,
                    "images": [img.group(1)] if img else []})
        if len(out) >= limit:
            break
    return out


def next_page_url(html: str) -> str | None:
    m = re.search(r'data-testid="catalog-pagination--next-page"[^>]*href="([^"]+)"', html)
    if not m:
        m = re.search(r'<a[^>]+href="([^"]*page=\d+[^"]*)"[^>]*>\s*(?:»|›|Weiter)', html)
    if not m:
        return None
    href = m.group(1).replace("&amp;", "&")
    return href if href.startswith("http") else f"https://www.vinted.de{href}"


HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
           "Accept-Language": "de-DE,de;q=0.9"}


class VintedDriver(MarketplaceDriver):
    manifest = DriverManifest(id="vinted", version="0.1.0", display_name="Vinted",
                              regions=["de", "at", "eu"], capabilities=["search", "images", "paged"],
                              access_mode="public_web", automation_permission="unknown", rate_limit_rpm=20)

    async def search(self, query: SearchQuery) -> list[CanonicalListing]:
        import asyncio as _aio
        url = f"https://www.vinted.de/catalog?search_text={quote_plus(query.keywords)}&order=relevance"
        if query.max_price:
            url += f"&price_to={int(query.max_price)}"
        items: list[dict] = []
        seen: set[str] = set()
        for _ in range(query.max_pages or 10):
            r = await self.transport.get(url, headers=HEADERS)
            if r.status_code in (401, 403):
                if not items:
                    raise RuntimeError(f"vinted blocked request ({r.status_code}) — retry later or via proxy")
                break
            r.raise_for_status()
            cards = parse_cards(r.text, 100)
            for it in cards:
                if it["id"] not in seen:
                    seen.add(it["id"])
                    items.append(it)
            if len(items) >= query.limit:
                break
            nxt = next_page_url(r.text)
            if not nxt:
                break
            url = nxt
            await _aio.sleep(2.0)
        if not items:
            raise RuntimeError("vinted returned no cards (empty or schema-change)")
        out: list[CanonicalListing] = []
        for it in items[:max(query.limit, 10)]:
            blob = it["title"].lower()
            out.append(CanonicalListing(
                id=f"vinted:{it['id']}", source="vinted", native_id=it["id"],
                url=it["url"], title=it["title"], price=it["price"], images=it["images"],
                shipping="buyer protection included in 2nd price" if it["price"] else "",
                pickup_available=("abholung" in blob),
                shipping_available=True))  # vinted is shipping-first marketplace
        if query.max_price is not None:
            out = [l for l in out if l.price is None or l.price <= query.max_price]
        return out[:query.limit]

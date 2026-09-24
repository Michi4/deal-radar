"""Willhaben driver — public web (permission: unknown; personal hobbyist use only).
Willhaben has bot detection; driver degrades cleanly and reports instead of failing silently.
Parsing is fixture-tested so frontend changes are caught by contract tests, not users.
"""
from __future__ import annotations
import re
from urllib.parse import quote_plus
from deal_radar.driver_sdk import MarketplaceDriver, DriverManifest, SearchQuery
from deal_radar.contracts import CanonicalListing, Seller


def parse_willhaben_html(html: str, limit: int = 20) -> list[dict]:
    """Parse search-result cards. Tolerant: returns [] on unknown markup (schema-change signal)."""
    cards: list[dict] = []
    # v1: data-testid cards / JSON-LD itemListElement
    for m in re.finditer(r'"name"\s*:\s*"([^"]{5,160})".*?"url"\s*:\s*"([^"]+)"', html):
        cards.append({"title": m.group(1), "url": m.group(2)})
        if len(cards) >= limit:
            break
    if not cards:
        for m in re.finditer(r'<a[^>]+href="(/iad/[^"]+)"[^>]*>([^<]{5,160})</a>', html):
            cards.append({"title": m.group(2).strip(), "url": "https://www.willhaben.at" + m.group(1)})
            if len(cards) >= limit:
                break
    out = []
    for c in cards[:limit]:
        price_m = None
        out.append({"title": c["title"], "url": c["url"], "price": price_m})
    return out


class WillhabenDriver(MarketplaceDriver):
    manifest = DriverManifest(id="willhaben", version="0.1.0", display_name="Willhaben",
                              regions=["at"], capabilities=["search", "images"],
                              access_mode="public_web", automation_permission="unknown", rate_limit_rpm=20)

    async def search(self, query: SearchQuery) -> list[CanonicalListing]:
        url = f"https://www.willhaben.at/iad/kaufen?KEYWORD={quote_plus(query.keywords)}"
        r = await self.transport.get(url, headers={"Accept-Language": "de-AT,de;q=0.9"})
        if r.status_code == 403:
            raise RuntimeError("willhaben blocked request (403, bot detection) — try proxy transport or later")
        r.raise_for_status()
        items = parse_willhaben_html(r.text, query.limit)
        if not items and len(r.text) > 1000:
            raise RuntimeError("willhaben markup changed (schema-change) — parser returned 0 items")
        out: list[CanonicalListing] = []
        for i, it in enumerate(items):
            out.append(CanonicalListing(id=f"willhaben:{abs(hash(it['url'])) % 10**10}_{i}",
                                        source="willhaben", native_id=it["url"], url=it["url"],
                                        title=it["title"], price=it.get("price")))
        return out

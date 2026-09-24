"""Kleinanzeigen driver — public web (permission: unknown; personal hobbyist use only)."""
from __future__ import annotations
import re
from urllib.parse import quote_plus
from deal_radar.driver_sdk import MarketplaceDriver, DriverManifest, SearchQuery
from deal_radar.contracts import CanonicalListing, Seller


def parse_kleinanzeigen_html(html: str, limit: int = 20) -> list[dict]:
    items: list[dict] = []
    for m in re.finditer(r'<article[^>]*class="[^"]*aditem[^"]*"[^>]*>(.*?)</article>', html, re.S):
        block = m.group(1)
        t = re.search(r'<a[^>]+class="[^"]*ellipsis[^"]*"[^>]*>([^<]{3,160})</a>', block)
        href = re.search(r'href="(/s-anzeige/[^"]+)"', block)
        p = re.search(r'(\d[\d\.\s]*)\s*€', block)
        img = re.search(r'<img[^>]+src="([^"]+)"', block)
        if t and href:
            price = float(p.group(1).replace(".", "").replace(" ", "")) if p else None
            items.append({"title": t.group(1).strip(),
                          "url": "https://www.kleinanzeigen.de" + href.group(1),
                          "price": price,
                          "image": img.group(1) if img else None})
        if len(items) >= limit:
            break
    return items


class KleinanzeigenDriver(MarketplaceDriver):
    manifest = DriverManifest(id="kleinanzeigen", version="0.1.0", display_name="Kleinanzeigen",
                              regions=["de"], capabilities=["search", "images"],
                              access_mode="public_web", automation_permission="unknown", rate_limit_rpm=30)

    async def search(self, query: SearchQuery) -> list[CanonicalListing]:
        url = f"https://www.kleinanzeigen.de/s-{quote_plus(query.keywords.replace(' ', '-'))}/k0"
        r = await self.transport.get(url, headers={"Accept-Language": "de-DE,de;q=0.9"})
        if r.status_code == 403:
            raise RuntimeError("kleinanzeigen blocked request (403) — try proxy transport or later")
        r.raise_for_status()
        items = parse_kleinanzeigen_html(r.text, query.limit)
        if not items and len(r.text) > 1000:
            raise RuntimeError("kleinanzeigen markup changed (schema-change) — parser returned 0 items")
        return [CanonicalListing(id=f"kleinanzeigen:{abs(hash(it['url'])) % 10**10}_{i}",
                                 source="kleinanzeigen", native_id=it["url"], url=it["url"],
                                 title=it["title"], price=it.get("price"),
                                 images=[it["image"]] if it.get("image") else [])
                for i, it in enumerate(items)]

"""eBay driver — official Browse API (permitted access mode). Clean reference driver.

NOTE (verified 2026-09-25): eBay's public search HTML is bot-walled — it returns decoy
template cards ("Shop on eBay", $ prices on .de, no real titles/prices) even with TLS
impersonation + session cookies. Scraping it would inject FAKE listings, so there is
deliberately NO web fallback. Get a free token: developer.ebay.com → Browse API
(self-authorized app) -> EBAY_OAUTH_TOKEN. Until then this driver reports cleanly."""
from __future__ import annotations

import os
from urllib.parse import quote_plus

from deal_radar.contracts import CanonicalListing, Seller
from deal_radar.driver_sdk import DriverManifest, MarketplaceDriver, SearchQuery


class EbayDriver(MarketplaceDriver):
    manifest = DriverManifest(id="ebay", version="0.1.0", display_name="eBay",
                              regions=["at", "de", "eu"], capabilities=["search", "fetch_detail", "images"],
                              access_mode="official_api", automation_permission="permitted", rate_limit_rpm=60)

    async def search(self, query: SearchQuery) -> list[CanonicalListing]:
        token = os.getenv("EBAY_OAUTH_TOKEN", "")
        if not token:
            raise RuntimeError("EBAY_OAUTH_TOKEN not set — configure eBay Browse API (see drivers/ebay/README.md)")
        market = os.getenv("EBAY_MARKETPLACE", "EBAY_AT")
        url = (f"https://api.ebay.com/buy/browse/v1/item_summary/search?q={quote_plus(query.keywords)}"
               f"&limit={min(query.limit, 50)}")
        if query.max_price:
            url += f"&filter=price:[..{query.max_price}],priceCurrency:EUR"
        r = await self.transport.get(url, headers={"Authorization": f"Bearer {token}",
                                                   "X-EBAY-C-MARKETPLACE-ID": market})
        r.raise_for_status()
        data = r.json()
        out: list[CanonicalListing] = []
        for it in data.get("itemSummaries", [])[:query.limit]:
            price = (it.get("price") or {}).get("value")
            out.append(CanonicalListing(
                id=f"ebay:{it.get('itemId', '')}", source="ebay", native_id=str(it.get("itemId", "")),
                url=it.get("itemWebUrl", ""), title=it.get("title", "")[:300],
                price=float(price) if price else None,
                currency=(it.get("price") or {}).get("currency", "EUR"),
                category=(it.get("categories") or [{}])[0].get("categoryName", "") if it.get("categories") else "",
                images=[it.get("image", {}).get("imageUrl")] if it.get("image", {}).get("imageUrl") else [],
                seller=Seller(name=(it.get("seller") or {}).get("username", "")),
                condition=(it.get("condition") or "")))
        return out

"""Brand-store driver (public Shopify products.json feeds — intended for consumption).

One generic engine, one instance per shop. The catalog is fetched (limit=250/page,
capped) and filtered client-side; cached in memory for an hour so repeated
searches cost nothing. Polite by construction: 1-3 requests per search, hourly.

Shops (verified live 2026-10-11, EUR storefronts unless noted):
- minisforum @ minisforumpc.eu (137 products, EUR, EU warehouse)
- gmktec @ de.gmktec.com (51 products, EUR)
- aoostar @ aoostar.com (25 products, EUR — EU-warehouse listings)
- acemagic @ www.acemagic.com (50 products, USD — global storefront)
"""
from __future__ import annotations

import re
import time

from deal_radar.contracts import CanonicalListing, Seller
from deal_radar.driver_sdk import DriverManifest, MarketplaceDriver, SearchQuery

_CATALOG: dict[str, tuple[float, list]] = {}
CATALOG_TTL = 3600.0
PAGE_CAP = 10


def _strip_html(raw: str) -> str:
    txt = re.sub(r"<[^>]+>", " ", raw or "")
    txt = txt.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
    return re.sub(r"\s+", " ", txt).strip()[:800]


def _match(blob: str, keywords: str) -> bool:
    words = [w for w in re.findall(r"[a-z0-9]+", keywords.lower()) if len(w) > 2]
    return bool(words) and all(w in blob for w in words)


class ShopifyDriver(MarketplaceDriver):
    manifest = DriverManifest(id="shopify", version="0.1.0", display_name="Shopify",
                              regions=["eu"], capabilities=["search", "images"],
                              access_mode="public_web", automation_permission="unknown",
                              rate_limit_rpm=20)

    def __init__(self, transport=None, shop_id: str = "", shop_name: str = "",
                 base_url: str = "", currency: str = "EUR"):
        super().__init__(transport)
        self.shop_id = shop_id or "shopify"
        self.shop_name = shop_name or base_url
        self.base_url = base_url.rstrip("/")
        self.currency = currency
        self.manifest = DriverManifest(
            id=self.shop_id, version="0.1.0", display_name=self.shop_name,
            regions=["eu"], capabilities=["search", "images"],
            access_mode="public_web", automation_permission="unknown", rate_limit_rpm=20)

    @staticmethod
    def configured() -> bool:
        return True  # public feeds, no credentials

    async def _catalog(self) -> list:
        now = time.time()
        hit = _CATALOG.get(self.shop_id)
        if hit and now - hit[0] < CATALOG_TTL:
            return hit[1]
        products: list = []
        for page in range(1, PAGE_CAP + 1):
            url = f"{self.base_url}/products.json?limit=250&page={page}"
            r = await self.transport.get(url, headers={"Accept": "application/json"})
            r.raise_for_status()
            batch = r.json().get("products", []) or []
            products.extend(batch)
            if len(batch) < 250:
                break
        _CATALOG[self.shop_id] = (now, products)
        return products

    async def search(self, query: SearchQuery) -> list[CanonicalListing]:
        products = await self._catalog()
        out: list[CanonicalListing] = []
        for p in products:
            title = str(p.get("title", "") or "")
            blob = f"{title} {' '.join(p.get('tags', []) or [])} {_strip_html(str(p.get('body_html', '') or ''))}".lower()
            if not _match(blob, query.keywords):
                continue
            variants = [v for v in (p.get("variants") or []) if isinstance(v, dict)]
            prices: list[float] = []
            for v in variants:
                try:
                    prices.append(float(str(v.get("price", "")).replace(",", ".")))
                except (TypeError, ValueError):
                    continue
            if not prices:
                continue
            price = min(prices)
            if query.max_price and price > query.max_price:
                continue
            if query.min_price and price < query.min_price:
                continue
            imgs = [str(i.get("src", "")) for i in (p.get("images") or []) if isinstance(i, dict) and i.get("src")]
            handle = str(p.get("handle", "") or p.get("id", ""))
            out.append(CanonicalListing(
                id=f"{self.shop_id}:{p.get('id', '')}", source=self.shop_id,
                native_id=str(p.get("id", "")),
                url=f"{self.base_url}/products/{handle}",
                title=f"{title} ({' / '.join(v.get('title', '') for v in variants[:3])})"[:300],
                description=_strip_html(str(p.get("body_html", "") or "")),
                price=price, currency=self.currency,
                images=imgs[:6], seller=Seller(name=self.shop_name),
                condition="new"))
            if len(out) >= query.limit:
                break
        return out


def make_shopify_driver(shop_id: str, shop_name: str, base_url: str, currency: str = "EUR") -> ShopifyDriver:
    return ShopifyDriver(transport=None, shop_id=shop_id, shop_name=shop_name,
                         base_url=base_url, currency=currency)


SHOPS = [
    ("minisforum", "Minisforum EU", "https://minisforumpc.eu", "EUR"),
    ("gmktec", "GMKtec DE", "https://de.gmktec.com", "EUR"),
    ("aoostar", "AOOSTAR", "https://aoostar.com", "EUR"),
    ("acemagic", "ACEMAGIC", "https://www.acemagic.com", "USD"),
]

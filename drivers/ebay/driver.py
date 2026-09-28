"""eBay driver — official Browse API (permitted access mode). Clean reference driver.

Auth paths (in order):
1. EBAY_OAUTH_TOKEN — hand-supplied user token (explicit override, shortest path).
2. EBAY_APP_ID + EBAY_CERT_ID — the app mints its own client-credentials token
   (POST api.ebay.com/identity/v1/oauth/token, scope buy.browse), caches it in
   memory + data/ebay_token.json, refreshes ~5 min before expiry. Paste the two
   values in Admin -> Secrets; no hand-copied token needed.
No keyless web fallback exists on purpose (verified 2026-09-25): eBay's public
search HTML is bot-walled and returns decoy template cards ("Shop on eBay", $ prices
on .de, no real titles/prices) even with TLS impersonation + session cookies.
Scraping it would inject FAKE listings. Without any credentials the driver raises a
clean error naming exactly which secrets to add.
"""
from __future__ import annotations

import os
import time
from urllib.parse import quote_plus

import httpx

from deal_radar.contracts import CanonicalListing, Seller
from deal_radar.driver_sdk import DriverManifest, MarketplaceDriver, SearchQuery

OAUTH_URL = "https://api.ebay.com/identity/v1/oauth/token"
OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope/buy.browse"
TOKEN_CACHE_PATH = "data/ebay_token.json"
_TOKEN_CACHE: dict = {}


def _cache_read() -> dict:
    try:
        import json as _j
        with open(TOKEN_CACHE_PATH, encoding="utf-8") as f:
            v = _j.load(f)
            return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def _cache_write(token: str, expires_at: float) -> None:
    try:
        import json as _j
        import os as _os
        _os.makedirs(_os.path.dirname(TOKEN_CACHE_PATH) or ".", exist_ok=True)
        with open(TOKEN_CACHE_PATH, "w", encoding="utf-8") as f:
            _j.dump({"access_token": token, "expires_at": expires_at}, f)
    except Exception:
        pass


async def mint_token(app_id: str, cert_id: str) -> tuple[str, float]:
    """Client-credentials grant. Returns (access_token, expires_at_epoch)."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            OAUTH_URL,
            auth=(app_id, cert_id),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": OAUTH_SCOPE})
    r.raise_for_status()
    body = r.json()
    token = str(body.get("access_token", ""))
    if not token:
        raise RuntimeError("eBay OAuth mint returned no access_token")
    expires_at = time.time() + int(body.get("expires_in", 7200))
    return token, expires_at


async def resolve_token() -> str:
    """Explicit token wins; else mint via App ID + Cert ID (cached, refreshed early)."""
    direct = os.getenv("EBAY_OAUTH_TOKEN", "").strip()
    if direct:
        return direct
    app_id = os.getenv("EBAY_APP_ID", "").strip()
    cert_id = os.getenv("EBAY_CERT_ID", "").strip()
    if not (app_id and cert_id):
        raise RuntimeError(
            "eBay needs credentials — either paste EBAY_OAUTH_TOKEN, or paste EBAY_APP_ID "
            "+ EBAY_CERT_ID (Admin -> Secrets) and the app mints its own token")
    if _TOKEN_CACHE.get("token") and _TOKEN_CACHE.get("expires_at", 0) - time.time() > 300:
        return str(_TOKEN_CACHE["token"])
    disk = _cache_read()
    if disk.get("access_token") and float(disk.get("expires_at", 0)) - time.time() > 300:
        _TOKEN_CACHE["token"] = disk["access_token"]
        _TOKEN_CACHE["expires_at"] = float(disk["expires_at"])
        return str(disk["access_token"])
    token, expires_at = await mint_token(app_id, cert_id)
    _TOKEN_CACHE["token"] = token
    _TOKEN_CACHE["expires_at"] = expires_at
    _cache_write(token, expires_at)
    return token


class EbayDriver(MarketplaceDriver):
    manifest = DriverManifest(id="ebay", version="0.2.0", display_name="eBay",
                              regions=["at", "de", "eu"], capabilities=["search", "fetch_detail", "images"],
                              access_mode="official_api", automation_permission="permitted", rate_limit_rpm=60)

    @staticmethod
    def configured() -> bool:
        if os.getenv("EBAY_OAUTH_TOKEN", "").strip():
            return True
        return bool(os.getenv("EBAY_APP_ID", "").strip() and os.getenv("EBAY_CERT_ID", "").strip())

    async def search(self, query: SearchQuery) -> list[CanonicalListing]:
        token = await resolve_token()
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

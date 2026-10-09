"""Allegro.pl driver — official REST API (permitted access mode).

Auth: ALLEGRO_CLIENT_ID + ALLEGRO_CLIENT_SECRET (self-serve at
apps.developer.allegro.pl, no approval needed for read-only). The app mints its
own application token (POST allegro.pl/auth/oauth/token, client_credentials
grant), caches it in memory + data/allegro_token.json, refreshes early.
Paste the two values in Admin -> Secrets.

Search: GET api.allegro.pl/offers/listing?phrase=... (public offer search works
with the application token). Shapes below follow developer.allegro.pl
(/documentation, GET /sale/offers + offers/listing contract) but are parsed
defensively — unknown fields never crash, missing fields become "".
Without credentials the driver raises a clean error naming the secrets.

NOT verified live yet (needs the 2-minute app registration by the owner) —
BLOCKERS.md tracks it. No scraping fallback: Allegro pages are bot-walled.
"""
from __future__ import annotations

import os
import time
from urllib.parse import quote_plus

import httpx

from deal_radar.contracts import CanonicalListing, Seller
from deal_radar.driver_sdk import DriverManifest, MarketplaceDriver, SearchQuery

OAUTH_URL = "https://allegro.pl/auth/oauth/token"
API_BASE = "https://api.allegro.pl"
TOKEN_CACHE_PATH = "data/allegro_token.json"
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


async def mint_token(client_id: str, client_secret: str) -> tuple[str, float]:
    """Client-credentials grant. Returns (access_token, expires_at_epoch)."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            OAUTH_URL,
            auth=(client_id, client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials"})
    r.raise_for_status()
    body = r.json()
    token = str(body.get("access_token", ""))
    if not token:
        raise RuntimeError("Allegro OAuth mint returned no access_token")
    expires_at = time.time() + int(body.get("expires_in", 43200))
    return token, expires_at


async def resolve_token() -> str:
    client_id = os.getenv("ALLEGRO_CLIENT_ID", "").strip()
    client_secret = os.getenv("ALLEGRO_CLIENT_SECRET", "").strip()
    if not (client_id and client_secret):
        raise RuntimeError(
            "Allegro needs credentials — paste ALLEGRO_CLIENT_ID + ALLEGRO_CLIENT_SECRET "
            "(Admin -> Secrets; self-serve at apps.developer.allegro.pl, read-only, "
            "no approval needed) and the app mints its own token")
    if _TOKEN_CACHE.get("token") and _TOKEN_CACHE.get("expires_at", 0) - time.time() > 300:
        return str(_TOKEN_CACHE["token"])
    disk = _cache_read()
    if disk.get("access_token") and float(disk.get("expires_at", 0)) - time.time() > 300:
        _TOKEN_CACHE["token"] = disk["access_token"]
        _TOKEN_CACHE["expires_at"] = float(disk["expires_at"])
        return str(disk["access_token"])
    token, expires_at = await mint_token(client_id, client_secret)
    _TOKEN_CACHE["token"] = token
    _TOKEN_CACHE["expires_at"] = expires_at
    _cache_write(token, expires_at)
    return token


def _parse_item(it: dict) -> CanonicalListing | None:
    try:
        oid = str(it.get("id", ""))
        if not oid:
            return None
        price = it.get("price") or it.get("sellingMode", {}).get("price") or {}
        amount = price.get("amount")
        try:
            amount_f = float(str(amount).replace(",", ".")) if amount else None
        except (TypeError, ValueError):
            amount_f = None
        imgs = it.get("images") or []
        img_urls = [str(x.get("url", "")) for x in imgs if isinstance(x, dict) and x.get("url")]
        if not img_urls:
            prim = it.get("primaryImage") or {}
            if prim.get("url"):
                img_urls = [str(prim["url"])]
        seller = it.get("seller") or {}
        cat = it.get("category") or {}
        return CanonicalListing(
            id=f"allegro:{oid}", source="allegro", native_id=oid,
            url=f"https://allegro.pl/oferta/{oid}",
            title=str(it.get("name", "") or "")[:300],
            price=amount_f, currency=str(price.get("currency", "PLN") or "PLN"),
            category=str(cat.get("name", "") or cat.get("id", "") or ""),
            images=img_urls[:8],
            seller=Seller(name=str(seller.get("name", "") or seller.get("id", "") or "")))
    except Exception:
        return None


class AllegroDriver(MarketplaceDriver):
    manifest = DriverManifest(id="allegro", version="0.1.0", display_name="Allegro",
                              regions=["pl", "eu"], capabilities=["search", "images"],
                              access_mode="official_api", automation_permission="permitted", rate_limit_rpm=60)

    @staticmethod
    def configured() -> bool:
        return bool(os.getenv("ALLEGRO_CLIENT_ID", "").strip()
                    and os.getenv("ALLEGRO_CLIENT_SECRET", "").strip())

    async def search(self, query: SearchQuery) -> list[CanonicalListing]:
        token = await resolve_token()
        headers = {"Authorization": f"Bearer {token}",
                   "Accept": "application/vnd.allegro.public.v1+json"}
        out: list[CanonicalListing] = []
        per_page = 120
        offset = 0
        max_pages = query.max_pages or 10**9
        pages = 0
        while len(out) < query.limit and pages < max_pages:
            url = (f"{API_BASE}/offers/listing?phrase={quote_plus(query.keywords)}"
                   f"&limit={min(per_page, query.limit)}&offset={offset}")
            if query.max_price:
                url += f"&price.to={query.max_price}"
            if query.min_price:
                url += f"&price.from={query.min_price}"
            r = await self.transport.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
            items = data.get("items", {})
            if isinstance(items, dict):
                batch = (items.get("regular", []) or []) + (items.get("promoted", []) or [])
            elif isinstance(items, list):
                batch = items
            else:
                batch = data.get("offers", []) or []
            if not batch:
                break
            for it in batch:
                if len(out) >= query.limit:
                    break
                parsed = _parse_item(it if isinstance(it, dict) else {})
                if parsed:
                    out.append(parsed)
            total = ((data.get("searchMeta") or {}).get("totalCount")
                     or data.get("totalCount") or 0)
            try:
                total = int(total)
            except (TypeError, ValueError):
                total = 0
            offset += len(batch)
            pages += 1
            if total and offset >= total:
                break
            if len(batch) < min(per_page, query.limit):
                break
        return out

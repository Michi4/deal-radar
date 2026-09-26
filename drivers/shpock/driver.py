"""Shpock driver — public web SSR (permission: unknown; personal hobbyist use only).

Strategy: search page embeds Next.js __NEXT_DATA__ with Apollo cache; ItemSummary
objects carry title/description/price/currency/path/canonicalURL/media/isSold/isShippable.
"""
from __future__ import annotations

import json
import re
from urllib.parse import quote_plus

from deal_radar.contracts import CanonicalListing
from deal_radar.driver_sdk import DriverManifest, MarketplaceDriver, SearchQuery


def parse_next_data(html: str, limit: int = 30) -> list[dict]:
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
    if not m:
        return []
    try:
        ap = json.loads(m.group(1))["props"]["pageProps"]["apolloState"]
    except Exception:
        return []
    out: list[dict] = []
    for key, ad in ap.items():
        if not key.startswith("ItemSummary:") or not isinstance(ad, dict):
            continue
        if ad.get("isSold") or ad.get("isExpired"):
            continue
        imgs = []
        media = ad.get("media")
        refs = media if isinstance(media, list) else []
        for med in refs[:6]:
            mid = (med or {}).get("id") if isinstance(med, dict) else None
            if not mid and isinstance(med, dict) and "__ref" in med:
                whole = ap.get(med["__ref"], {})
                mid = whole.get("id") if isinstance(whole, dict) else None
            if mid:
                imgs.append(f"https://m1.secondhandapp.at/2.0/{mid}?height=1024&width=1024")
        price = ad.get("price")
        try:
            price = float(price) if price is not None else None
        except (ValueError, TypeError):
            price = None
        cur = str(ad.get("currency", "EUR") or "EUR").upper()
        cur = {"EUR": "EUR", "EURO": "EUR"}.get(cur, cur)
        path = ad.get("path") or ad.get("canonicalURL") or ""
        url = path if path.startswith("http") else f"https://www.shpock.com{path}"
        out.append({"id": str(ad.get("id", "")), "title": str(ad.get("title", ""))[:300],
                    "description": str(ad.get("description", ""))[:2000], "price": price,
                    "currency": cur, "url": url,
                    "images": imgs, "shippable": bool(ad.get("isShippable", False))})
        if len(out) >= limit:
            break
    return out


HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
           "Accept-Language": "de-AT,de;q=0.9"}


class ShpockDriver(MarketplaceDriver):
    manifest = DriverManifest(id="shpock", version="0.1.0", display_name="Shpock",
                              regions=["at", "de"], capabilities=["search", "images", "shipping"],
                              access_mode="public_web", automation_permission="unknown", rate_limit_rpm=20)

    async def search(self, query: SearchQuery) -> list[CanonicalListing]:
        url = f"https://www.shpock.com/de/search?q={quote_plus(query.keywords)}"
        r = await self.transport.get(url, headers=HEADERS)
        if r.status_code in (401, 403):
            raise RuntimeError(f"shpock blocked request ({r.status_code}) — retry later or via proxy")
        r.raise_for_status()
        items = parse_next_data(r.text, query.limit)
        if not items and len(r.text) > 5000:
            raise RuntimeError("shpock markup changed (schema-change) — no ItemSummary objects")
        out: list[CanonicalListing] = []
        for it in items:
            blob = f"{it['title']} {it['description']}".lower()
            out.append(CanonicalListing(
                id=f"shpock:{it['id']}", source="shpock", native_id=it["id"], url=it["url"],
                title=it["title"], description=it["description"], price=it["price"],
                currency=it["currency"], images=it["images"],
                pickup_available=any(k in blob for k in ("abholung", "selbstabholung")),
                shipping_available=it["shippable"] or any(k in blob for k in ("versand",))))
        if query.max_price is not None:
            out = [l for l in out if l.price is None or l.price <= query.max_price]
        return out[:query.limit]

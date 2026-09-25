"""Willhaben driver — public web (permission: unknown; personal hobbyist use only).

Strategy (researched Sep 2026): plain httpx GET on the marktplatz search URL,
parse Next.js __NEXT_DATA__ -> props.pageProps.searchResult.advertSummaryList.advertSummary
(fallback: initialSearchResult), DOM fallback on a[data-testid^='search-result-entry-header-'].
Bot detection: silent 403/empty on datacenter IPs -> back off, report cleanly, retry via proxy.
"""
from __future__ import annotations

import json
import re
from datetime import UTC
from urllib.parse import quote_plus

from deal_radar.contracts import CanonicalListing, Seller
from deal_radar.driver_sdk import DriverManifest, MarketplaceDriver, SearchQuery


def _flatten_attrs(ad: dict) -> dict:
    out: dict = {}
    for a in (ad.get("attributes", {}).get("attribute") or []):
        name = str(a.get("name", "")).upper()
        vals = a.get("values") or []
        if vals:
            out[name] = vals[0] if len(vals) == 1 else vals
    return out


def parse_next_data(html: str, limit: int = 30) -> list[dict]:
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    page = (data.get("props", {}).get("pageProps", {}) or {})
    sr = page.get("searchResult") or page.get("initialSearchResult") or {}
    ads = ((sr.get("advertSummaryList") or {}).get("advertSummary")) or []
    out: list[dict] = []
    for ad in ads[:limit]:
        at = _flatten_attrs(ad)
        seo = at.get("SEO_URL", "")
        url = f"https://www.willhaben.at/iad/{seo}" if seo else ""
        price_raw = at.get("PRICE", "")
        price = None
        if price_raw not in ("", None):
            try:
                price = float(str(price_raw).replace(".", "").replace(",", ".").replace("€", "").strip())
            except ValueError:
                price = None
        imgs = []
        for im in ((ad.get("advertImageList") or {}).get("advertImage") or []):
            u = im.get("mainImageUrl") or im.get("referenceImageUrl")
            if u:
                imgs.append(u if u.startswith("http") else f"https:{u}")
        body = at.get("BODY_DYN", "") or ad.get("description", "")
        loc = at.get("LOCATION", "") or at.get("ADDRESS", "")
        out.append({
            "id": str(ad.get("id", "")),
            "title": str(at.get("HEADING", ""))[:300],
            "url": url,
            "price": price,
            "description": str(body)[:2000],
            "location": str(loc),
            "postcode": str(at.get("POSTCODE", "")),
            "images": imgs,
            "seller": str(at.get("ORGNAME", "")),
            "private": at.get("ISPRIVATE", True),
        })
    return out


def parse_dom_fallback(html: str, limit: int = 30) -> list[dict]:
    out: list[dict] = []
    for m in re.finditer(r'<a[^>]+data-testid="search-result-entry-header-[^"]*"[^>]+href="([^"]+)"[^>]*>.*?<h3[^>]*>([^<]{3,200})</h3>', html, re.DOTALL):
        href, title = m.group(1), m.group(2).strip()
        url = href if href.startswith("http") else f"https://www.willhaben.at{href}"
        out.append({"id": url, "title": title, "url": url, "price": None, "description": "",
                    "location": "", "postcode": "", "images": [], "seller": "", "private": True})
        if len(out) >= limit:
            break
    return out


def parse_detail(html: str) -> dict:
    """advertDetails from /iad/object?adId= — full description + seller profile."""
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
    if not m:
        return {}
    try:
        ad = json.loads(m.group(1)).get("props", {}).get("pageProps", {}).get("advertDetails", {})
    except Exception:
        return {}
    at = _flatten_attrs(ad)
    sp = ad.get("sellerProfileUserData") or {}
    age = None
    if sp.get("registerDate"):
        try:
            from datetime import datetime
            reg = datetime.fromisoformat(str(sp["registerDate"]))
            age = max(0, (datetime.now(UTC) - reg).days)
        except Exception:
            pass
    price = None
    if at.get("PRICE"):
        try:
            price = float(str(at["PRICE"]).replace(".", "").replace(",", "."))
        except ValueError:
            pass
    return {"description": str(ad.get("description", ""))[:4000], "price": price,
            "seller": str(sp.get("name", "")), "account_age_days": age,
            "location": str(sp.get("location", "")) or str(sp.get("district", ""))}


HEADERS = {"Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
           "Accept": "text/html,application/xhtml+xml",
           "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}


class WillhabenDriver(MarketplaceDriver):
    manifest = DriverManifest(id="willhaben", version="0.3.0", display_name="Willhaben",
                              regions=["at"], capabilities=["search", "fetch_detail", "images", "location", "seller"],
                              access_mode="public_web", automation_permission="unknown", rate_limit_rpm=20)

    async def search(self, query: SearchQuery) -> list[CanonicalListing]:
        rows = 90  # max per page: over-fetch, filter/rank locally (one request)
        url = (f"https://www.willhaben.at/iad/kaufen-und-verkaufen/marktplatz"
               f"?KEYWORD={quote_plus(query.keywords)}&rows={rows}&sort=1")
        if query.max_price:
            url += f"&PRICE_TO={int(query.max_price)}"
        r = await self.transport.get(url, headers=HEADERS)
        if r.status_code == 403:
            raise RuntimeError("willhaben blocked request (403, bot detection) — retry later or via AT proxy")
        r.raise_for_status()
        items = parse_next_data(r.text, query.limit) or parse_dom_fallback(r.text, query.limit)
        if not items and len(r.text) > 5000:
            raise RuntimeError("willhaben markup changed (schema-change) — __NEXT_DATA__ + DOM both empty")
        out: list[CanonicalListing] = []
        for it in items:
            blob = f"{it['title']} {it['description']}".lower()
            pickup = any(k in blob for k in ("abholung", "selbstabholung", "pickup"))
            shipping = any(k in blob for k in ("versand", "paylivery", "shipping"))
            out.append(CanonicalListing(
                id=f"willhaben:{it['id'] or abs(hash(it['url'])) % 10**10}", source="willhaben",
                native_id=str(it["id"] or it["url"]), url=it["url"], title=it["title"],
                description=it["description"], price=it["price"], location=it["location"],
                postcode=it["postcode"], images=it["images"],
                seller=Seller(name=it["seller"]), shipping="",
                pickup_available=pickup, shipping_available=shipping))
        return out

    async def fetch_detail(self, native_id_or_url: str) -> CanonicalListing | None:
        import re as _re
        m = _re.search(r"(\d{6,})", native_id_or_url)
        if not m:
            return None
        url = f"https://www.willhaben.at/iad/object?adId={m.group(1)}"
        r = await self.transport.get(url, headers=HEADERS)
        r.raise_for_status()
        d = parse_detail(r.text)
        if not d:
            return None
        return CanonicalListing(id=f"willhaben:{m.group(1)}", source="willhaben",
                                native_id=m.group(1), url=url,
                                description=d.get("description", ""), price=d.get("price"),
                                location=d.get("location", ""),
                                seller=Seller(name=d.get("seller", ""),
                                              account_age_days=d.get("account_age_days")))

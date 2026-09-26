"""Ricardo.ch driver — public web SSR (permission: unknown; personal hobbyist use only).

Strategy: search page embeds per-article JSON (buyNowPrice in centimes, bidsCount,
sellerId, shipping, image URLs) next to /de/a/{slug}-{id}/ links. Prices may be absent
for pure auctions without buy-now — those get price=None, never dropped.
CHF amounts are centimes: 3550 -> CHF 35.50.
"""
from __future__ import annotations

import re
from urllib.parse import quote_plus

from deal_radar.contracts import CanonicalListing, Seller
from deal_radar.driver_sdk import DriverManifest, MarketplaceDriver, SearchQuery


def parse_cards(html: str, limit: int = 30) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    # primary: embedded "articles" JSON array (double-escaped in page source)
    clean = html.replace('\\"', '"').replace("\\\\", "\\")
    m = re.search(r'"articles":\[(.*)\]\s*,\s*"[a-zA-Z]+":', clean, re.DOTALL)
    if m:
        for chunk in re.split(r'\{"id":"', m.group(1))[1:]:
            idm = re.match(r"(\d+)\"", chunk)
            if not idm:
                continue
            adid = idm.group(1)
            if adid in seen:
                continue
            seen.add(adid)
            seg = chunk[:3000]
            tm = re.search(r'"title":"((?:[^"\\]|\\.)*)"', seg)
            title = tm.group(1) if tm else ""
            try:
                title = title.encode().decode("unicode_escape", errors="ignore")
            except Exception:
                pass
            pm = re.search(r'"buyNowPrice":(\d+|null)', seg)
            price = int(pm.group(1)) / 100.0 if pm and pm.group(1) != "null" else None
            img = re.search(r'"image":"(https://img\.ricardostatic\.ch/[^"]+)"', seg)
            loc = re.search(r'"city":"([^"]{1,80})"', seg)
            seller = re.search(r'"sellerId":"?(\d+)"?', seg)
            url_m = re.search(r'"url":"(/de/a/[^"]+)"', seg)
            url = f"https://www.ricardo.ch{url_m.group(1)}" if url_m else \
                f"https://www.ricardo.ch/de/a/-{adid}/"
            if not title:
                continue
            out.append({"id": adid, "title": title[:300], "url": url, "price": price,
                        "images": [img.group(1)] if img else [],
                        "seller": seller.group(1) if seller else "",
                        "location": loc.group(1) if loc else "", "shipping": True})
            if len(out) >= limit:
                return out
        if out:
            return out
    # fallback: card links
    links = [(m.start(), m.group(1), m.group(2)) for m in
             re.finditer(r'href="(/de/a/[^"]*?(\d+)/?)"', html)]
    for idx, (pos, href, adid) in enumerate(links):
        if adid in seen:
            continue
        seen.add(adid)
        end = links[idx + 1][0] if idx + 1 < len(links) else pos + 6000
        block = html[pos:end][:6000]
        title = re.search(r"<span[^>]*>([^<]{4,160})</span>", block)
        title = (title.group(1).strip() if title else "") or ""
        title = title.replace("&quot;", '"').replace("&amp;", "&")
        price = None
        m = re.search(r'"buyNowPrice":(\d+)', block)
        if m:
            try:
                price = int(m.group(1)) / 100.0
            except ValueError:
                price = None
        img = re.search(r"https://img\.ricardostatic\.ch/images/[a-z0-9\-]+/t_265x200/[a-z0-9\-\(\)\.,_ ]+", block)
        seller = re.search(r'"sellerId":"?(\d+)"?', block)
        loc = re.search(r'"city":"([^"]{1,80})"', block)
        ship = "parcel" in block or "versand" in block.lower()
        url = href if href.startswith("http") else f"https://www.ricardo.ch{href}"
        if not title:
            continue
        out.append({"id": adid, "title": title, "url": url, "price": price,
                    "images": [img.group(0)] if img else [],
                    "seller": seller.group(1) if seller else "",
                    "location": loc.group(1) if loc else "",
                    "shipping": ship})
        if len(out) >= limit:
            break
    return out


HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
           "Accept-Language": "de-CH,de;q=0.9"}


class RicardoDriver(MarketplaceDriver):
    manifest = DriverManifest(id="ricardo", version="0.1.0", display_name="Ricardo",
                              regions=["ch"], capabilities=["search", "images", "location"],
                              access_mode="public_web", automation_permission="unknown", rate_limit_rpm=20)

    def __init__(self, transport=None):
        from deal_radar.driver_sdk import TlsImpersonatingTransport
        super().__init__(transport or TlsImpersonatingTransport("chrome124"))

    async def search(self, query: SearchQuery) -> list[CanonicalListing]:
        url = f"https://www.ricardo.ch/de/s/{quote_plus(query.keywords)}"
        r = await self.transport.get(url, headers=HEADERS)
        if r.status_code in (401, 403):
            raise RuntimeError(f"ricardo blocked request ({r.status_code}) — retry later or via proxy")
        r.raise_for_status()
        items = parse_cards(r.text, query.limit)
        if not items and len(r.text) > 5000:
            raise RuntimeError("ricardo markup changed (schema-change) — no cards parsed")
        out: list[CanonicalListing] = []
        for it in items:
            blob = it["title"].lower()
            out.append(CanonicalListing(
                id=f"ricardo:{it['id']}", source="ricardo", native_id=it["id"], url=it["url"],
                title=it["title"], price=it["price"], currency="CHF", location=it["location"],
                images=it["images"], seller=Seller(name=it["seller"]),
                pickup_available=("abholung" in blob),
                shipping_available=it["shipping"] or ("versand" in blob)))
        if query.max_price is not None:
            out = [l for l in out if l.price is None or l.price <= query.max_price]
        return out[:query.limit]

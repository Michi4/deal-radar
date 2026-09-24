"""Kleinanzeigen driver — public web (permission: unknown; personal hobbyist use only).

Strategy (researched Sep 2026): keyword search at /s-{slug}/k0, browser-like headers,
sequential requests, parse article[data-adid] (2026 layout) with legacy .aditem fallback.
Never template category page-2 URLs — follow #srchrslt-pagination hrefs.
"""
from __future__ import annotations
import re
import unicodedata
from urllib.parse import quote
from deal_radar.driver_sdk import MarketplaceDriver, DriverManifest, SearchQuery
from deal_radar.contracts import CanonicalListing, Seller


def slugify(keywords: str) -> str:
    s = unicodedata.normalize("NFKD", keywords.lower()).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "suchbegriff"


def parse_price(raw: str) -> tuple[float | None, str]:
    t = (raw or "").strip()
    if not t:
        return None, t
    if "verschenken" in t.lower() or "gratis" in t.lower():
        return 0.0, t
    m = re.search(r"(\d[\d\.\s]*)\s*€?", t)
    if not m:
        return None, t
    try:
        return float(m.group(1).replace(".", "").replace(" ", "").replace(",", ".")), t
    except ValueError:
        return None, t


def parse_cards(html: str, limit: int = 25) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    # 2026 layout: article[data-adid] + data-href
    for m in re.finditer(r'<article[^>]*data-adid="(\d+)"[^>]*data-href="([^"]+)"[^>]*>(.*?)</article>', html, re.S):
        adid, href, block = m.group(1), m.group(2), m.group(3)
        if adid in seen:
            continue
        seen.add(adid)
        title = re.search(r"<h3[^>]*>([^<]{2,200})</h3>", block)
        price = re.search(r'<p[^>]*class="[^"]*text-secondary[^"]*"[^>]*>([^<]{1,60})</p>', block)
        desc = re.search(r'<p[^>]*class="[^"]*text-bodyRegular[^"]*"[^>]*>([^<]{0,500})</p>', block)
        addr = re.search(r'text-onSurfaceNonessential[^>]*>\s*<span[^>]*>([^<]{1,120})</span>', block)
        img = re.search(r'<img[^>]+src="([^"]+)"', block)
        p, praw = parse_price(price.group(1) if price else "")
        url = href if href.startswith("http") else f"https://www.kleinanzeigen.de{href}"
        out.append({"id": adid, "title": (title.group(1).strip() if title else ""),
                    "url": url, "price": p, "price_raw": praw,
                    "description": (desc.group(1).strip() if desc else ""),
                    "location": (addr.group(1).strip() if addr else ""),
                    "images": [img.group(1)] if img else []})
        if len(out) >= limit:
            return out
    if out:
        return out
    # legacy layout fallback: article.aditem / .ad-listitem
    for m in re.finditer(r'<article[^>]*class="[^"]*aditem[^"]*"[^>]*>(.*?)</article>', html, re.S):
        block = m.group(1)
        a = re.search(r'<a[^>]*class="[^"]*ellipsis[^"]*"[^>]*href="([^"]+)"[^>]*>\s*([^<]+?)\s*</a>', block)
        if not a:
            continue
        href, title = a.group(1), a.group(2).strip()
        if href in seen:
            continue
        seen.add(href)
        p_el = re.search(r"<p[^>]*>([^<]*€[^<]*|VB|Zu verschenken)</p>", block)
        d_el = re.search(r'aditem-main--middle--description[^>]*>([^<]{0,500})', block)
        loc_el = re.search(r'aditem-main--top--left[^>]*>.*?([A-ZÄÖÜ][^<]{1,80})<', block, re.S)
        img = re.search(r'<img[^>]+(?:src|data-src)="([^"]+)"', block)
        p, praw = parse_price(p_el.group(1) if p_el else "")
        url = href if href.startswith("http") else f"https://www.kleinanzeigen.de{href}"
        out.append({"id": href, "title": title, "url": url, "price": p, "price_raw": praw,
                    "description": (d_el.group(1).strip() if d_el else ""),
                    "location": (loc_el.group(1).strip() if loc_el else ""),
                    "images": [img.group(1)] if img else []})
        if len(out) >= limit:
            break
    return out


def next_page_url(html: str) -> str | None:
    m = re.search(r'<div[^>]*id="srchrslt-pagination"[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>\s*(?:»|Weiter|next)', html, re.S | re.I)
    if not m:
        return None
    href = m.group(1)
    return href if href.startswith("http") else f"https://www.kleinanzeigen.de{href}"


HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
           "Accept-Language": "de-DE,de;q=0.9", "Upgrade-Insecure-Requests": "1"}


class KleinanzeigenDriver(MarketplaceDriver):
    manifest = DriverManifest(id="kleinanzeigen", version="0.2.0", display_name="Kleinanzeigen",
                              regions=["de"], capabilities=["search", "images", "location"],
                              access_mode="public_web", automation_permission="unknown", rate_limit_rpm=30)

    async def search(self, query: SearchQuery) -> list[CanonicalListing]:
        url = f"https://www.kleinanzeigen.de/s-{slugify(query.keywords)}/k0"
        r = await self.transport.get(url, headers=HEADERS)
        if r.status_code == 403:
            raise RuntimeError("kleinanzeigen blocked request (403) — retry later or via DE proxy")
        r.raise_for_status()
        items = parse_cards(r.text, query.limit)
        if not items and len(r.text) > 5000:
            raise RuntimeError("kleinanzeigen markup changed (schema-change) — no cards parsed")
        out: list[CanonicalListing] = []
        for it in items:
            blob = f"{it['title']} {it['description']}".lower()
            pickup = any(k in blob for k in ("abholung", "selbstabholung", "abholer"))
            shipping = any(k in blob for k in ("versand", "verschicke", "dhl", "hermes", "porto"))
            loc = it["location"]
            pc = re.search(r"\b\d{5}\b", loc)
            out.append(CanonicalListing(
                id=f"kleinanzeigen:{it['id']}", source="kleinanzeigen", native_id=str(it["id"]),
                url=it["url"], title=it["title"], description=it["description"], price=it["price"],
                location=loc, postcode=pc.group(0) if pc else "", images=it["images"],
                shipping=it.get("price_raw", ""), pickup_available=pickup, shipping_available=shipping))
        # hard price pre-filter when supported (site ignores it for keyword URLs, so post-filter)
        if query.max_price is not None:
            out = [l for l in out if l.price is None or l.price <= query.max_price]
        return out[:query.limit]

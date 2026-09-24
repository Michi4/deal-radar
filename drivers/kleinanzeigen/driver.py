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


def _ld_block(block: str) -> dict:
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', block, re.S)
    if not m:
        return {}
    try:
        import json as _json
        return _json.loads(m.group(1))
    except Exception:
        return {}


def parse_cards(html: str, limit: int = 25) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for m in re.finditer(r'<article[^>]*data-adid="(\d+)"[^>]*data-href="([^"]+)"[^>]*>(.*?)</article>', html, re.S):
        adid, href, block = m.group(1), m.group(2), m.group(3)
        if adid in seen:
            continue
        seen.add(adid)
        ld = _ld_block(block)
        t = re.search(r"<h3[^>]*>\s*<a[^>]*>([^<]{2,300})</a>", block)
        title = (t.group(1).strip() if t else ld.get("title", "")).replace("&quot;", '"').replace("&amp;", "&")
        d = re.search(r"</h3>\s*<p[^>]*>([^<]{0,600})</p>", block)
        desc = (d.group(1).strip() if d else ld.get("description", ""))[:600]
        p = re.search(r"<p[^>]*>\s*(\d[\d\.\s]*)\s*€", block)
        price, praw = parse_price(p.group(1) if p else "")
        loc = re.search(r'data-title="locationOutline".*?<span[^>]*>([^<]{1,120})</span>', block, re.S)
        location = loc.group(1).strip() if loc else ""
        img = re.search(r'<img[^>]+src="([^"]+)"', block)
        image = img.group(1) if img else ld.get("contentUrl", "")
        ship_badge = "data-dhl-promotion" in block or "Versand möglich" in block
        blob = f"{title} {desc}".lower()
        shipping = ship_badge or any(k in blob for k in ("versand", "verschicke", "dhl", "hermes", "porto"))
        pickup = any(k in blob for k in ("abholung", "selbstabholung", "abholer"))
        url = href if href.startswith("http") else f"https://www.kleinanzeigen.de{href}"
        out.append({"id": adid, "title": title, "url": url, "price": price, "price_raw": praw,
                    "description": desc, "location": location,
                    "images": [image] if image else [],
                    "pickup": pickup, "shipping": shipping})
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
            pcm = re.search(r"\b\d{5}\b", it["location"] or "")
            out.append(CanonicalListing(
                id=f"kleinanzeigen:{it['id']}", source="kleinanzeigen", native_id=str(it["id"]),
                url=it["url"], title=it["title"], description=it["description"], price=it["price"],
                location=it["location"], postcode=pcm.group(0) if pcm else "", images=it["images"],
                shipping=it.get("price_raw", ""), pickup_available=it.get("pickup", False),
                shipping_available=it.get("shipping", False)))
        # hard price pre-filter when supported (site ignores it for keyword URLs, so post-filter)
        if query.max_price is not None:
            out = [l for l in out if l.price is None or l.price <= query.max_price]
        return out[:query.limit]

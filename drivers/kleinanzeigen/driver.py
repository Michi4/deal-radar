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


def parse_detail(html: str) -> dict:
    """Ad detail page: full description, attributes, price, seller type, images."""
    out: dict = {"attributes": {}, "images": []}
    m = re.search(r'<p id="viewad-description-text"[^>]*itemprop="description"[^>]*>(.*?)</p>', html, re.S)
    if m:
        out["description"] = re.sub(r"<[^>]+>", " ", m.group(1))
        out["description"] = re.sub(r"\s+", " ", out["description"]).strip()[:4000]
    for lm in re.finditer(r'class="addetailslist--detail[^"]*"[^>]*>(.*?)</li>', html, re.S):
        txt = re.sub(r"<[^>]+>", "|", lm.group(1))
        parts = [p.strip() for p in txt.split("|") if p.strip()]
        if len(parts) >= 2:
            out["attributes"][parts[0][:60]] = parts[-1][:200]
    pm = re.search(r'itemprop="price"[^>]*content="([\d.]+)"', html)
    if pm:
        try:
            out["price"] = float(pm.group(1))
        except ValueError:
            pass
    blob = html.lower()
    out["commercial"] = "gewerblich" in blob
    loc = re.search(r'id="viewad-locality"[^>]*>([^<]{1,120})<', html)
    if loc:
        out["location"] = loc.group(1).strip()
    for im in re.finditer(r'"contentUrl":"(https://img\.kleinanzeigen\.de/[^"]+)"', html):
        u = im.group(1)
        if u not in out["images"]:
            out["images"].append(u)
        if len(out["images"]) >= 8:
            break
    return out


HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
           "Accept-Language": "de-DE,de;q=0.9", "Upgrade-Insecure-Requests": "1"}


class KleinanzeigenDriver(MarketplaceDriver):
    manifest = DriverManifest(id="kleinanzeigen", version="0.4.0", display_name="Kleinanzeigen",
                              regions=["de"], capabilities=["search", "fetch_detail", "images", "location", "paged"],
                              access_mode="public_web", automation_permission="unknown", rate_limit_rpm=30)

    async def _fetch_page(self, url: str) -> tuple[list[dict], str | None]:
        import asyncio as _aio
        r = await self.transport.get(url, headers=HEADERS)
        if r.status_code == 403:
            raise RuntimeError("kleinanzeigen blocked request (403) — retry later or via DE proxy")
        r.raise_for_status()
        return parse_cards(r.text, 100), next_page_url(r.text)

    async def search(self, query: SearchQuery) -> list[CanonicalListing]:
        import asyncio as _aio
        url = f"https://www.kleinanzeigen.de/s-{slugify(query.keywords)}/k0"
        items: list[dict] = []
        seen_urls: set[str] = set()
        for _page in range(3):  # sequential + polite delay; never concurrent from one IP
            try:
                cards, nxt = await self._fetch_page(url)
            except RuntimeError:
                if not items:
                    raise
                break
            for it in cards:
                if it["url"] not in seen_urls:
                    seen_urls.add(it["url"])
                    items.append(it)
            if len(items) >= query.limit or not nxt:
                break
            url = nxt
            await _aio.sleep(2.5)
        if not items:
            raise RuntimeError("kleinanzeigen returned no cards (empty or schema-change)")
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

    async def fetch_detail(self, native_id_or_url: str) -> CanonicalListing | None:
        m = re.search(r"/s-anzeige/([^/]+/)?(\d+)", native_id_or_url)
        url = native_id_or_url if native_id_or_url.startswith("http") else \
            f"https://www.kleinanzeigen.de/s-anzeige/{m.group(2)}" if m else None
        if not url:
            return None
        r = await self.transport.get(url, headers=HEADERS)
        r.raise_for_status()
        d = parse_detail(r.text)
        if not d.get("description"):
            return None
        adid = m.group(2) if m else url
        return CanonicalListing(id=f"kleinanzeigen:{adid}", source="kleinanzeigen", native_id=adid,
                                url=url, description=d.get("description", ""),
                                price=d.get("price"), location=d.get("location", ""),
                                images=d.get("images", []),
                                attributes=d.get("attributes", {}),
                                seller=Seller(name="pro" if d.get("commercial") else ""))

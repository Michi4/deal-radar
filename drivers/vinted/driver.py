"""Vinted driver — public web SSR (permission: unknown; personal hobbyist use only).

Strategy: catalog search page is server-rendered with item cards
(data-testid product-item-id-*-overlay-link, price in img alt text incl. fees).
Sequential pages via catalog-pagination--next-page link.
"""
from __future__ import annotations

import re
from typing import ClassVar
from urllib.parse import quote_plus

from deal_radar.contracts import CanonicalListing
from deal_radar.driver_sdk import (
    DriverManifest,
    MarketplaceDriver,
    SearchQuery,
    eu_price,
)


def _unesc(s: str) -> str:
    return s.replace("&quot;", '"').replace("&amp;", "&").replace("&#x27;", "'").strip()


def parse_cards(html: str, limit: int = 30) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for m in re.finditer(
            r'<a[^>]+href="(/items/\d+[^"]*)"[^>]*data-testid="product-item-id-(\d+)--overlay-link"[^>]*title="([^"]{3,300})"',
            html):
        href, adid, title = m.group(1), m.group(2), _unesc(m.group(3))
        if adid in seen:
            continue
        seen.add(adid)
        url = href if href.startswith("http") else f"https://www.vinted.de{href.split('?')[0]}"
        # price: look for the card's img alt "...., 140.00 €, 147.70 €" (price, +protection total)
        block = html[max(0, m.start() - 1500):m.start()]
        prices = re.findall(r"([\d][\d\.\s,]*)\s*€", block[-800:])
        price = eu_price(prices[0]) if prices else None
        img = re.search(r'<img[^>]+src="(https://images\d*\.vinted\.net/[^"]+)"[^>]*>$', block[-800:]) or \
            re.search(r'src="(https://images\d*\.vinted\.net/[^"]+)"', block[-800:])
        out.append({"id": adid, "title": title, "url": url, "price": price,
                    "images": [img.group(1)] if img else []})
        if len(out) >= limit:
            break
    return out


def next_page_url(html: str) -> str | None:
    m = re.search(r'data-testid="catalog-pagination--next-page"[^>]*href="([^"]+)"', html)
    if not m:
        m = re.search(r'<a[^>]+href="([^"]*page=\d+[^"]*)"[^>]*>\s*(?:»|›|Weiter)', html)
    if not m:
        return None
    href = m.group(1).replace("&amp;", "&")
    return href if href.startswith("http") else f"https://www.vinted.de{href}"


def parse_catalog_links(html: str) -> list[dict]:
    """Category tree the site itself links: /catalog/<id>-<slug> nav hrefs."""
    import html as _h
    out: list[dict] = []
    seen: set[str] = set()
    for m in re.finditer(r'href="(/catalog/(\d+)-([a-z0-9_]+)[^"]*)"', html):
        cid, slug = m.group(2), m.group(3)
        if cid in seen:
            continue
        seen.add(cid)
        label = _h.unescape(m.group(1)).split("?")[0]
        out.append({"id": cid, "slug": slug, "href": label,
                    "label": slug.replace("_root", "").replace("_", " ").title()})
    return out


def _vcat_cache_read(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            d = __import__("json").load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _vcat_cache_write(path: str, cache: dict) -> None:
    try:
        import os as _os
        _os.makedirs(_os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            __import__("json").dump(cache, f)
    except Exception:
        pass


HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
           "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
           "Accept-Language": "de-DE,de;q=0.9"}


class VintedDriver(MarketplaceDriver):
    manifest = DriverManifest(id="vinted", version="0.2.0", display_name="Vinted",
                              regions=["de", "at", "eu"], capabilities=["search", "images", "paged"],
                              access_mode="public_web", automation_permission="unknown", rate_limit_rpm=20)

    # Catalog tree read live 2026-09-28 from the site's own /catalog nav. id -> label.
    CATEGORIES: ClassVar[dict] = {
        "5": "Men", "1193": "Children New",
        "1904": "Women", "1918": "Home",
        "2309": "Entertainment", "2994": "Electronics",
        "4332": "Sports", "4824": "Hobbies Collectables"}
    # Sub-catalogs under Electronics (verified live 2026-09-28 by drilling /catalog/2994).
    SUBCATEGORIES: ClassVar[dict] = {
        "2995": "Electronics Accessories",
        "3002": "Video Games",
        "3004": "Wearables",
        "3054": "Cameras Accessories",
        "3564": "Computers",
        "3565": "Phones",
        "3566": "Audio",
        "3567": "Tablets Acc",
        "3568": "TV",
        "3569": "Beauty"}
    # Path slugs per tree id (the site addresses /catalog/<id>-<slug>).
    CAT_SLUGS: ClassVar[dict] = {
        "5": "mens", "1193": "children_new",
        "1904": "women_root", "1918": "home",
        "2309": "entertainment", "2994": "electronics",
        "4332": "sports", "4824": "hobbies_collectables",
        "2995": "electronics_accessories",
        "3002": "electronics_video_games",
        "3004": "electronics_wearables",
        "3054": "electronics_cameras_accessories",
        "3564": "electronics_computers",
        "3565": "electronics_phones",
        "3566": "electronics_audio",
        "3567": "electronics_tablets_acc",
        "3568": "electronics_tv",
        "3569": "electronics_beauty"}
    CATEGORY_CACHE_TTL_S: ClassVar[int] = 7 * 24 * 3600

    @classmethod
    def resolve_category(cls, value: str | None) -> tuple[str, str] | None:
        """Tree id, slug, or label -> (id, slug). None if unknown."""
        v = (value or "").strip()
        if not v:
            return None
        tree = {**cls.CATEGORIES, **cls.SUBCATEGORIES}
        if v in tree:
            return (v, cls.CAT_SLUGS[v])
        low = v.lower()
        for cid, label in tree.items():
            if cls.CAT_SLUGS.get(cid, "") == low or label.lower() == low:
                return (cid, cls.CAT_SLUGS[cid])
        return None

    def search_url(self, query: SearchQuery) -> str:
        cat = self.resolve_category((query.cat_map or {}).get("vinted", "") or query.category)
        if cat:
            url = (f"https://www.vinted.de/catalog/{cat[0]}-{cat[1]}"
                   f"?search_text={quote_plus(query.keywords)}&order=relevance")
        else:
            url = f"https://www.vinted.de/catalog?search_text={quote_plus(query.keywords)}&order=relevance"
        if query.max_price:
            url += f"&price_to={int(query.max_price)}"
        return url

    def category_cache_path(self) -> str:
        import os as _os
        return _os.path.join("data", "vinted_categories.json")

    async def fetch_categories(self, parent: str | None = None) -> dict:
        """Live sub-tree from the site's own catalog nav, disk-cached 7d."""
        import time as _t
        if not parent:
            return {"categories": [{"label": v, "id": k, "slug": self.CAT_SLUGS.get(k, "")}
                                   for k, v in self.CATEGORIES.items()]}
        resolved = self.resolve_category(parent)
        if resolved is None:
            raise RuntimeError(f"unknown vinted category {parent!r}")
        cid, slug = resolved
        cache: dict = _vcat_cache_read(self.category_cache_path())
        hit = (cache.get("parents") or {}).get(cid)
        if hit and _t.time() - hit.get("ts", 0) < self.CATEGORY_CACHE_TTL_S:
            return hit["data"]
        url = f"https://www.vinted.de/catalog/{cid}-{slug}?order=relevance"
        r = await self.transport.get(url, headers=HEADERS)
        r.raise_for_status()
        cats = [{"label": c["label"], "id": c["id"], "slug": c["slug"],
                 "param": "catalog-path"} for c in parse_catalog_links(r.text)
                if c["id"] != cid]
        data = {"selected": [{"param": "catalog-path", "value": cid, "label": slug}],
                "categories": cats, "rowsFound": None}
        cache.setdefault("parents", {})[cid] = {"ts": _t.time(), "data": data}
        _vcat_cache_write(self.category_cache_path(), cache)
        return data

    async def search(self, query: SearchQuery) -> list[CanonicalListing]:
        import asyncio as _aio
        url = self.search_url(query)
        items: list[dict] = []
        seen: set[str] = set()
        for _ in range(query.max_pages or 10**9):  # walk to exhaustion (breaks when no next page)
            from deal_radar.cancel import pause_gate as _pg
            from deal_radar.cancel import should_stop as _ss
            if _ss(query.sid):
                break
            if await _pg(query.sid):
                break
            r = await self.transport.get(url, headers=HEADERS)
            if r.status_code in (401, 403):
                if not items:
                    raise RuntimeError(f"vinted blocked request ({r.status_code}) — retry later or via proxy")
                break
            r.raise_for_status()
            cards = parse_cards(r.text, 100)
            for it in cards:
                if it["id"] not in seen:
                    seen.add(it["id"])
                    items.append(it)
            if len(items) >= query.limit:
                break
            nxt = next_page_url(r.text)
            if not nxt:
                break
            url = nxt
            await _aio.sleep(2.0)
        if not items:
            raise RuntimeError("vinted returned no cards (empty or schema-change)")
        out: list[CanonicalListing] = []
        for it in items[:max(query.limit, 10)]:
            blob = it["title"].lower()
            out.append(CanonicalListing(
                id=f"vinted:{it['id']}", source="vinted", native_id=it["id"],
                url=it["url"], title=it["title"], price=it["price"], images=it["images"],
                shipping="buyer protection included in 2nd price" if it["price"] else "",
                pickup_available=("abholung" in blob),
                shipping_available=True))  # vinted is shipping-first marketplace
        if query.max_price is not None:
            out = [l for l in out if l.price is None or l.price <= query.max_price]
        return out[:query.limit]

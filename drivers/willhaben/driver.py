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
from typing import ClassVar
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


def parse_next_data(html: str, limit: int = 30) -> tuple[list[dict], int | None]:
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
    if not m:
        return [], None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return [], None
    page = (data.get("props", {}).get("pageProps", {}) or {})
    sr = page.get("searchResult") or page.get("initialSearchResult") or {}
    total = sr.get("rowsFound") or sr.get("total")
    try:
        total = int(total) if total is not None else None
    except (ValueError, TypeError):
        total = None
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
        tree_ids = str(at.get("categorytreeids", "") or at.get("CATEGORYTREEIDS", ""))
        out.append({
            "id": str(ad.get("id", "")),
            "category_tree_ids": tree_ids,
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
    return out, total


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


def parse_navigators(sr: dict) -> dict:
    """Category/facet tree the site itself embeds (navigatorGroups).

    Returns {"categories": [{"label", "id", "param"}], "selected": [{"param", "value", "label"}]}.
    Category filter param is ATTRIBUTE_TREE (numeric tree id); attribute facets use treeAttributes.
    """
    cats: list[dict] = []
    selected: list[dict] = []
    for g in (sr.get("navigatorGroups") or []):
        for nav in (g.get("navigatorList") or []):
            for v in (nav.get("selectedValues") or []):
                for u in (v.get("urlParamRepresentationForValue") or []):
                    selected.append({"param": u.get("urlParameterName"),
                                     "value": u.get("value"), "label": v.get("label")})
            if nav.get("id") != "category":
                continue
            groups = nav.get("groupedPossibleValues") or []
            vals = list(nav.get("possibleValues") or [])
            for gg in groups:
                vals.extend(gg.get("possibleValues") or [])
            for v in vals:
                ups = v.get("urlParamRepresentationForValue") or []
                if not ups:
                    continue
                cats.append({"label": str(v.get("label") or ""),
                             "id": str(ups[0].get("value") or ""),
                             "param": str(ups[0].get("urlParameterName") or "")})
    return {"categories": [c for c in cats if c["id"]], "selected": selected}


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
            "title": str(at.get("HEADING", ""))[:300],
            "seller": str(sp.get("name", "")), "account_age_days": age,
            "location": str(sp.get("location", "")) or str(sp.get("district", ""))}


HEADERS = {"Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
           "Accept": "text/html,application/xhtml+xml",
           "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}


def _cat_cache_read(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _cat_cache_write(path: str, cache: dict) -> None:
    try:
        import os as _os
        _os.makedirs(_os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except Exception:
        pass


class WillhabenDriver(MarketplaceDriver):
    manifest = DriverManifest(id="willhaben", version="0.3.0", display_name="Willhaben",
                              regions=["at"], capabilities=["search", "fetch_detail", "images", "location", "seller"],
                              access_mode="public_web", automation_permission="unknown", rate_limit_rpm=20)

    # Bundesland -> areaId, extracted live 2026-09-27 from marktplatz __NEXT_DATA__
    # (navigator "Bundesland"). Verified: areaId=900 returns Vienna-only results.
    AREAS: ClassVar[dict] = {"burgenland": "1", "kärnten": "2", "kaernten": "2",
                             "niederösterreich": "3", "niederoesterreich": "3",
                             "oberösterreich": "4", "oberoesterreich": "4",
                             "salzburg": "5", "steiermark": "6", "tirol": "7",
                             "vorarlberg": "8", "wien": "900", "vienna": "900"}

    # Top-level marktplatz category tree, read live 2026-09-28 from the site's own
    # navigatorGroups facet (ATTRIBUTE_TREE=<id>). id -> label; sub-trees via fetch_categories().
    CATEGORIES: ClassVar[dict] = {
        "6941": "Antiquitäten / Kunst", "3928": "Baby / Kind",
        "3076": "Beauty / Gesundheit / Wellness", "5007823": "Boote / Yachten / Jetskis",
        "387": "Bücher / Filme / Musik", "5824": "Computer / Software",
        "537": "Dienstleistungen", "6462": "Freizeit / Instrumente / Kulinarik",
        "2785": "Games / Konsolen", "3541": "Haus / Garten / Werkstatt",
        "6808": "Kameras / TV / Multimedia", "6142": "KFZ-Zubehör / Motorradteile",
        "3275": "Mode / Accessoires", "2691": "Smartphones / Telefonie",
        "5136": "Spielen / Spielzeug", "4390": "Sport / Sportgeräte",
        "4915": "Tiere / Tierbedarf", "2409": "Uhren / Schmuck",
        "5387": "Wohnen / Haushalt / Gastronomie"}
    # Known sub-categories (verified live 2026-09-28 by drilling ATTRIBUTE_TREE).
    SUBCATEGORIES: ClassVar[dict] = {
        "5825": "Adapter / Kabel", "5828": "Computer / Tablets",
        "5836": "Drucker / Monitore / Lautsprecher", "5852": "Eingabe- / Lesegeräte",
        "5867": "Festplatten / Speicherkarten", "5871": "Netzwerke",
        "5878": "PC-Komponenten", "5891": "Software", "5901": "USB-Zubehör",
        "2692": "Handyservices", "2764": "Organizer / PDAs",
        "2722": "Smartphones / Handys", "2771": "Smartwatches", "2772": "Tablets",
        "2765": "Telefonie / Fax", "2750": "Zubehör Handy / Telefonie"}
    CATEGORY_CACHE_TTL_S: ClassVar[int] = 7 * 24 * 3600

    @classmethod
    def resolve_category(cls, value: str | None) -> str | None:
        """Numeric tree id passes through; labels resolve via the known tree. None if unknown."""
        v = (value or "").strip()
        if not v:
            return None
        if v.isdigit():
            return v
        low = v.lower()
        for cid, label in {**cls.CATEGORIES, **cls.SUBCATEGORIES}.items():
            if label.lower() == low:
                return cid
        return None

    def search_url(self, query: SearchQuery) -> str:
        base = (f"https://www.willhaben.at/iad/kaufen-und-verkaufen/marktplatz"
                f"?keyword={quote_plus(query.keywords)}&rows=90&sort=1")
        # NOTE: lowercase `keyword` — uppercase KEYWORD silently returns the UNFILTERED
        # marketplace (13M rows). Verified live 2026-09-26.
        if query.max_price:
            base += f"&PRICE_TO={int(query.max_price)}"
        # category: per-driver override wins, then generic category (id or label)
        cat = self.resolve_category((query.cat_map or {}).get("willhaben", "") or query.category)
        if cat:
            base += f"&ATTRIBUTE_TREE={cat}"
        # delivery facets (verified live 2026-09-28: server-side filter, both = union)
        if query.require_pickup:
            base += "&treeAttributes=2536"
        if query.require_shipping:
            base += "&treeAttributes=2537"
        # geo: Bundesland-level (?areaId=), cities/postcodes fall back to keywords
        loc = (query.location or "").strip().lower()
        if loc and loc in self.AREAS:
            base += f"&areaId={self.AREAS[loc]}"
        return base

    def category_cache_path(self) -> str:
        import os as _os
        return _os.path.join("data", "wh_categories.json")

    async def fetch_categories(self, parent: str | None = None) -> dict:
        """Live category (sub-)tree from the site's own navigators, disk-cached 7d.

        parent=None -> top 19 (static snapshot, no fetch). parent=<tree id> -> one polite
        fetch of a filtered search page, returns selected + sub-categories + rowsFound.
        """
        import json as _json
        import time as _t
        if not parent:
            return {"categories": [{"label": v, "id": k, "param": "ATTRIBUTE_TREE"}
                                   for k, v in self.CATEGORIES.items()]}
        cp = self.category_cache_path()
        cache: dict = _cat_cache_read(cp)
        hit = (cache.get("parents") or {}).get(str(parent))
        if hit and _t.time() - hit.get("ts", 0) < self.CATEGORY_CACHE_TTL_S:
            return hit["data"]
        url = ("https://www.willhaben.at/iad/kaufen-und-verkaufen/marktplatz"
               f"?rows=5&sort=1&ATTRIBUTE_TREE={quote_plus(str(parent))}")
        r = await self.transport.get(url, headers=HEADERS)
        r.raise_for_status()
        m = __import__("re").search(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text, __import__("re").DOTALL)
        if not m:
            raise RuntimeError("willhaben category drill: no __NEXT_DATA__ (blocked or markup changed)")
        sr = _json.loads(m.group(1)).get("props", {}).get("pageProps", {}).get("searchResult", {})
        nav = parse_navigators(sr)
        data = {"selected": nav["selected"], "categories": nav["categories"],
                "rowsFound": sr.get("rowsFound")}
        cache.setdefault("parents", {})[str(parent)] = {"ts": _t.time(), "data": data}
        _cat_cache_write(cp, cache)
        return data

    async def search(self, query: SearchQuery) -> list[CanonicalListing]:
        import asyncio as _aio
        base = self.search_url(query)
        max_pages = query.max_pages or 10**9  # walk to exhaustion (breaks on empty page)
        items: list[dict] = []
        seen: set[str] = set()
        for page_no in range(1, max_pages + 1):  # sequential, polite
            from deal_radar.cancel import pause_gate as _pg
            from deal_radar.cancel import should_stop as _ss
            if _ss(query.sid):
                break
            if await _pg(query.sid):
                break
            url = f"{base}&page={page_no}"
            r = await self.transport.get(url, headers=HEADERS)
            if r.status_code == 403:
                if not items:
                    raise RuntimeError("willhaben blocked request (403, bot detection) — retry later or via AT proxy")
                break
            r.raise_for_status()
            cards, total = parse_next_data(r.text, 90)
            if total is not None and total > 1000000 and query.keywords:
                # server ignored the keyword (unfiltered dump) — flag loudly, keep client-side filtering
                from deal_radar import metrics as _mx
                _mx.inc("willhaben_unfiltered_dump")
                print(f"[willhaben] WARNING: query {query.keywords!r} returned {total} rows (unfiltered?)",
                      flush=True)
            if not cards:
                cards = parse_dom_fallback(r.text, 90)
                total = None
            if not cards and len(r.text) > 5000 and not items:
                raise RuntimeError("willhaben markup changed (schema-change) — __NEXT_DATA__ + DOM both empty")
            new = 0
            for it in cards:
                if it["url"] not in seen:
                    seen.add(it["url"])
                    items.append(it)
                    new += 1
            if total is not None and len(items) >= total:
                break  # every page collected
            if new == 0 or (total is None and page_no >= 3 and len(items) >= query.limit):
                break
            if page_no > 1:
                await _aio.sleep(1.2)
        out: list[CanonicalListing] = []
        for it in items:
            blob = f"{it['title']} {it['description']}".lower()
            pickup = any(k in blob for k in ("abholung", "selbstabholung", "pickup"))
            shipping = any(k in blob for k in ("versand", "paylivery", "shipping"))
            out.append(CanonicalListing(
                id=f"willhaben:{it['id'] or abs(hash(it['url'])) % 10**10}", source="willhaben",
                native_id=str(it["id"] or it["url"]), url=it["url"], title=it["title"],
                description=it["description"], price=it["price"],
                attributes={"category_tree_ids": it.get("category_tree_ids", "")},
                location=it["location"],
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
                                native_id=m.group(1), url=url, title=d.get("title", ""),
                                description=d.get("description", ""), price=d.get("price"),
                                location=d.get("location", ""),
                                seller=Seller(name=d.get("seller", ""),
                                              account_age_days=d.get("account_age_days")))

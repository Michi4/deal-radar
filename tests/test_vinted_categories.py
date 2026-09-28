"""Vinted categories from the site's own catalog nav (path /catalog/<id>-<slug>).

Fixture = real trimmed capture (first 200KB) of
https://www.vinted.de/catalog?search_text=iphone&order=relevance (2026-09-28).
Trimmed only (nav links live at the top); parsing asserts against real markup.
"""
from pathlib import Path

from vinted.driver import VintedDriver, parse_catalog_links

from deal_radar.driver_sdk import SearchQuery

FIX = Path(__file__).parent / "fixtures" / "vinted-catalog-nav.html"


def test_top_level_catalogs_from_real_nav():
    cats = parse_catalog_links(FIX.read_text())
    by_id = {c["id"]: c for c in cats}
    assert len(cats) >= 8
    assert by_id["2994"]["slug"] == "electronics"
    assert by_id["5"]["slug"] == "mens"


def test_search_url_uses_catalog_path():
    d = VintedDriver()
    q = SearchQuery(keywords="iphone", cat_map={"vinted": "3565"})
    u = d.search_url(q)
    assert "/catalog/3565-electronics_phones" in u and "search_text=iphone" in u
    q2 = SearchQuery(keywords="iphone")
    assert u != d.search_url(q2) and "/catalog?" in d.search_url(q2)


def test_resolve_category_labels_and_ids():
    d = VintedDriver()
    assert d.resolve_category("3565") == ("3565", "electronics_phones")
    assert d.resolve_category("electronics_phones") == ("3565", "electronics_phones")
    assert d.resolve_category("Phones") == ("3565", "electronics_phones")
    assert d.resolve_category("") is None
    assert d.resolve_category("nope-not-a-cat") is None

"""Willhaben categories from the site's own facet tree (ATTRIBUTE_TREE).

Fixture = real captured navigatorGroups (keyword=iphone, 2026-09-28).
"""
import json
from pathlib import Path

from willhaben.driver import WillhabenDriver, parse_navigators

from deal_radar.driver_sdk import SearchQuery

FIX = Path(__file__).parent / "fixtures" / "willhaben-navigators-iphone.json"


def _sr():
    return {"navigatorGroups": json.loads(FIX.read_text())["navigatorGroups"]}


def test_top_level_tree_has_19_categories():
    cats = parse_navigators(_sr())["categories"]
    assert len(cats) == 19
    by_label = {c["label"]: c["id"] for c in cats}
    assert by_label["Smartphones / Telefonie"] == "2691"
    assert by_label["Computer / Software"] == "5824"
    assert all(c["id"].isdigit() for c in cats)


def test_selected_values_reported():
    nav = parse_navigators(_sr())
    assert ("keyword", "iphone") in [(s["param"], s["value"]) for s in nav["selected"]]


def test_search_url_uses_attribute_tree_for_category():
    d = WillhabenDriver()
    q = SearchQuery(keywords="iphone", cat_map={"willhaben": "2722"})
    assert "ATTRIBUTE_TREE=2722" in d.search_url(q)
    q2 = SearchQuery(keywords="iphone")
    assert "ATTRIBUTE_TREE" not in d.search_url(q2)


def test_category_label_resolves_via_static_tree():
    d = WillhabenDriver()
    assert d.resolve_category("Smartphones / Handys") == "2722"
    assert d.resolve_category("2722") == "2722"
    assert d.resolve_category("") is None


def test_ad_carries_category_tree_ids():
    from willhaben.driver import parse_next_data
    html = (Path(__file__).parent / "fixtures" / "willhaben-search.html").read_text()
    cards, _ = parse_next_data(html, 5)
    assert cards, "real willhaben-search.html fixture must yield cards"

import pytest

pytestmark = pytest.mark.live


def test_willhaben_category_search_live():
    """ATTRIBUTE_TREE=2722 (Smartphones/Handys) + keyword filters server-side."""
    import asyncio

    from willhaben.driver import WillhabenDriver

    from deal_radar.driver_sdk import SearchQuery

    async def go():
        d = WillhabenDriver()
        out = await d.search(SearchQuery(keywords="iphone", cat_map={"willhaben": "2722"},
                                        limit=10, max_pages=1))
        assert len(out) >= 1, "category-filtered search must return listings"
        assert out[0].title and out[0].url.startswith("https://www.willhaben.at/iad/")
        tids = [l.attributes.get("category_tree_ids", "") for l in out]
        assert any("2722" in t or "2691" in t for t in tids), f"ads carry tree ids: {tids[:3]}"
    asyncio.run(go())


def test_willhaben_category_drill_live():
    """Sub-tree drill reads the site's own navigators (one polite cached fetch)."""
    import asyncio

    from willhaben.driver import WillhabenDriver

    async def go():
        d = WillhabenDriver()
        data = await d.fetch_categories("2691")
        labels = [c["label"] for c in data["categories"]]
        assert "Smartphones / Handys" in labels
        assert data["rowsFound"] and data["rowsFound"] > 1000
    asyncio.run(go())

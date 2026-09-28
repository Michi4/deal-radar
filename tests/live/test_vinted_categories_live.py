import pytest

pytestmark = pytest.mark.live


def test_vinted_category_search_live():
    """Catalog path 3565-electronics_phones + keyword filters server-side."""
    import asyncio

    from vinted.driver import VintedDriver

    from deal_radar.driver_sdk import SearchQuery

    async def go():
        d = VintedDriver()
        out = await d.search(SearchQuery(keywords="iphone", cat_map={"vinted": "3565"},
                                        limit=6, max_pages=1))
        assert len(out) >= 1, "category-filtered search must return listings"
        assert out[0].title and "/items/" in out[0].url
    asyncio.run(go())


def test_vinted_category_drill_live():
    """Sub-tree drill reads the site's own catalog nav (one polite cached fetch)."""
    import asyncio

    from vinted.driver import VintedDriver

    async def go():
        d = VintedDriver()
        data = await d.fetch_categories("2994")
        slugs = [c["slug"] for c in data["categories"]]
        assert "electronics_phones" in slugs
        assert len(data["categories"]) >= 8
    asyncio.run(go())

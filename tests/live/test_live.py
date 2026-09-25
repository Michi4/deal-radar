import pytest

pytestmark = pytest.mark.live

def test_willhaben_detail_live():
    import asyncio

    from willhaben.driver import WillhabenDriver
    async def go():
        d = await WillhabenDriver().fetch_detail("866637457")
        assert d and d.price == 8.0 and d.seller.account_age_days is not None
        assert "Selbstabholung" in d.description
    asyncio.run(go())

def test_kleinanzeigen_search_live():
    import asyncio

    from kleinanzeigen.driver import KleinanzeigenDriver

    from deal_radar.driver_sdk import SearchQuery
    async def go():
        out = await KleinanzeigenDriver().search(SearchQuery(keywords="ThinkPad", limit=5))
        assert len(out) >= 1 and out[0].title and out[0].url
    asyncio.run(go())


def test_willhaben_search_live():
    import asyncio

    from willhaben.driver import WillhabenDriver

    from deal_radar.driver_sdk import SearchQuery
    async def go():
        out = await WillhabenDriver().search(SearchQuery(keywords="ThinkPad", limit=5))
        assert len(out) >= 1 and out[0].title
    asyncio.run(go())

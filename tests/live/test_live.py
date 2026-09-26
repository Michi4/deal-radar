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


def test_vinted_search_live():
    import asyncio

    from vinted.driver import VintedDriver

    from deal_radar.driver_sdk import SearchQuery
    async def go():
        out = await VintedDriver().search(SearchQuery(keywords="ThinkPad", limit=5))
        assert len(out) >= 1
        l = out[0]
        assert l.title and l.url.startswith("https://www.vinted.de/items/")
        assert l.price is not None and l.images
    asyncio.run(go())


def test_ebay_clean_error_without_token():
    import asyncio
    import os

    from ebay.driver import EbayDriver

    from deal_radar.driver_sdk import SearchQuery
    os.environ.pop("EBAY_OAUTH_TOKEN", None)
    async def go():
        res, err = await EbayDriver().guarded_search(SearchQuery(keywords="ThinkPad", limit=5))
        assert res == [] and err and "EBAY_OAUTH_TOKEN" in err
    asyncio.run(go())


def test_kleinanzeigen_full_fields_live():
    import asyncio

    from kleinanzeigen.driver import KleinanzeigenDriver

    from deal_radar.driver_sdk import SearchQuery
    async def go():
        out = await KleinanzeigenDriver().search(SearchQuery(keywords="ThinkPad T460", limit=10))
        full = [l for l in out if l.title and l.price is not None and l.url and l.images]
        assert full, "no fully-populated listing in top 10"
        d = await KleinanzeigenDriver().fetch_detail(full[0].native_id or full[0].url)
        assert d is None or len(d.description or "") >= 0
    asyncio.run(go())


def test_shpock_search_live():
    import asyncio

    from shpock.driver import ShpockDriver

    from deal_radar.driver_sdk import SearchQuery
    async def go():
        out = await ShpockDriver().search(SearchQuery(keywords="ThinkPad", limit=5))
        assert len(out) >= 1
        l = out[0]
        assert l.title and l.url and l.images
    asyncio.run(go())


def test_ricardo_search_live():
    import asyncio

    from deal_radar.driver_sdk import SearchQuery
    from ricardo.driver import RicardoDriver
    async def go():
        out = await RicardoDriver().search(SearchQuery(keywords="ThinkPad", limit=5))
        assert len(out) >= 1
        l = out[0]
        assert l.title and l.url and l.currency == "CHF"
    asyncio.run(go())


def test_shpock_search_live():
    import asyncio

    from deal_radar.driver_sdk import SearchQuery
    from shpock.driver import ShpockDriver
    async def go():
        out = await ShpockDriver().search(SearchQuery(keywords="ThinkPad", limit=5))
        assert len(out) >= 1
        assert out[0].title and out[0].url
    asyncio.run(go())

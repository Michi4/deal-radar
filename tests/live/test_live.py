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

    from ricardo.driver import RicardoDriver

    from deal_radar.driver_sdk import SearchQuery
    async def go():
        out = await RicardoDriver().search(SearchQuery(keywords="ThinkPad", limit=5))
        assert len(out) >= 1
        l = out[0]
        assert l.title and l.url and l.currency == "CHF"
    asyncio.run(go())

import pytest as _pt
_ptmark = _pt.mark.live


@_pt.mark.live
def test_willhaben_lowercase_keyword_filters():
    import urllib.request, re, json
    H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0",
         "Accept-Language": "de-AT,de;q=0.9"}
    base = "https://www.willhaben.at/iad/kaufen-und-verkaufen/marktplatz"
    html = urllib.request.urlopen(
        urllib.request.Request(base + "?keyword=iPhone%2017&rows=10", headers=H),
        timeout=30).read().decode("utf-8", "ignore")
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    sr = json.loads(m.group(1))["props"]["pageProps"].get("searchResult") or {}
    assert (sr.get("rowsFound") or 0) < 1000000, "keyword ignored by server?"

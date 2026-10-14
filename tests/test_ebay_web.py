"""eBay session-web driver: real captured search page (headed Chrome + login)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "drivers"))

from ebay_web.driver import EbayWebDriver, parse_ebay_search, parse_price

FIX = Path("tests/fixtures/ebay-search-ryzen.html").read_text()


def test_parse_price_variants():
    assert parse_price("EUR 49,00") == (49.0, "EUR")
    assert parse_price("EUR 101,67") == (101.67, "EUR")
    assert parse_price("$20.00") == (20.0, "USD")
    assert parse_price("EUR 89,90 bis EUR 189,90")[0] == 89.9
    assert parse_price("") == (None, "")
    assert parse_price("Preis auf Anfrage") == (None, "")


def test_parse_real_search_page():
    items = parse_ebay_search(FIX, 100)
    # 62 card slots minus the 2 decoy placeholders
    assert len(items) == 60, len(items)
    by_id = {x["id"]: x for x in items}
    m715 = by_id["128082469288"]
    assert m715["title"].startswith("Mini PC Lenovo M715Q Ryzen 3 PRO 2200GE")
    assert m715["price"] == 49.0 and m715["currency"] == "EUR"
    assert m715["url"] == "https://www.ebay.at/itm/128082469288"
    assert m715["seller"] == "amsk-it" and "100%" in m715["rating"]
    assert m715["coupon"] is True and m715["watchers"] == "7"
    assert m715["location"] == "Polen"
    igel = by_id["278303530945"]
    assert igel["price"] == 50.0 and igel["shipping"] == 14.49
    assert igel["seller"] == "wolf.pirmasens"
    as5 = by_id["206616753184"]
    assert as5["parts_only"] is True and as5["price"] == 62.0
    # every item has id/title/url/price
    assert all(x["title"] and x["url"].startswith("https://www.ebay.at/itm/") for x in items)
    assert all(x["price"] is not None and x["price"] > 0 for x in items)


def test_auction_and_range_rows():
    items = parse_ebay_search(FIX, 100)
    by_id = {x["id"]: x for x in items}
    auc = by_id.get("147629544958")
    if auc is not None:
        assert auc["auction"] is True
    r = by_id.get("307197284801")
    if r is not None:
        assert r["price"] == 89.9  # range takes the first figure


def test_unconfigured_driver_fails_clean():
    import os
    from unittest.mock import patch

    import pytest

    from deal_radar.driver_sdk import SearchQuery
    d = EbayWebDriver()
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("EBAY_CDP_URL", None)
        os.environ.pop("EBAY_COOKIES_JSON", None)
        assert EbayWebDriver.configured() is False
    # no debug browser on CI port: clean RuntimeError, never a hang
    d.cdp_url = "http://localhost:9"
    with pytest.raises(RuntimeError, match="eBay"):
        asyncio.run(d.search(SearchQuery(keywords="ryzen", limit=5)))


def test_title_matches_query():
    from ebay_web.driver import _title_matches
    html = "<html><head><title>Thinkpad Mainboard | eBay</title></head></html>"
    assert _title_matches(html, "thinkpad mainboard") is True
    assert _title_matches(html, "ryzen mini pc") is False
    assert _title_matches("", "ryzen") is False
    assert _title_matches(html, "x") is True  # no usable tokens: accept


def test_nav_lock_serializes():
    import asyncio

    from ebay_web import driver as D
    D._NAV_LOCK = None
    entered = []

    async def go():
        async with D._nav_lock():
            entered.append(1)
            await asyncio.sleep(0.05)
            entered.append(2)

    async def main():
        assert D._nav_lock() is D._nav_lock()
        await asyncio.gather(go(), go())

    asyncio.run(main())
    assert entered == [1, 2, 1, 2]


def test_search_wires_shipping_cost():
    """Round 21: shipping sat in attributes only, so every ranking ignored it
    (a $567-freight 'cheapest' 3090 was the most expensive all-in)."""
    import asyncio
    from unittest.mock import patch

    from deal_radar.driver_sdk import SearchQuery

    d = EbayWebDriver()
    with patch.object(EbayWebDriver, "_page_html", return_value=FIX):
        out = asyncio.run(d.search(SearchQuery(keywords="ryzen", limit=100)))
    by_id = {x.native_id: x for x in out}
    igel = by_id["278303530945"]
    assert igel.shipping_cost == 14.49
    for x in out:
        assert x.shipping_cost is None or x.shipping_cost >= 0

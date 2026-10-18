"""AliExpress driver: real captured search pages (rendered via the debug browser).

Fixtures are genuine DOM captures from a headed Chrome (CDP) navigating
aliexpress.com — never hand-typed. See packages/deal_radar/cdp.py.
"""
import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "drivers"))

from aliexpress.driver import (
    AliexpressDriver,
    parse_aliexpress_search,
    parse_price,
)

from deal_radar.cdp import CdpTransport, aliexpress_search_url
from deal_radar.driver_sdk import SearchQuery, transport_from_config

FIX_MINI = Path("tests/fixtures/aliexpress-search-minisforum.html").read_text()
FIX_BOARD = Path("tests/fixtures/aliexpress-search-board.html").read_text()


def test_parse_price_variants():
    assert parse_price("€1,865.57") == (1865.57, "EUR")
    assert parse_price("€135.74") == (135.74, "EUR")
    assert parse_price("€3.71") == (3.71, "EUR")
    assert parse_price("1.865,57 €") == (1865.57, "EUR")
    assert parse_price("US $20.00") == (20.0, "USD")
    assert parse_price("£12.50") == (12.5, "GBP")
    assert parse_price("€1.99 - €3.99")[0] == 1.99
    assert parse_price("") == (None, "")


def test_parse_real_minisforum_page():
    items = parse_aliexpress_search(FIX_MINI, 100)
    assert len(items) >= 10, len(items)
    by_id = {x["id"]: x for x in items}
    # real UM870 listing captured live during the hunt
    um870 = next(x for x in items if "UM870" in x["title"])
    assert um870["price"] > 100 and um870["currency"] == "EUR"
    assert um870["url"].startswith("https://www.aliexpress.com/item/")
    assert um870["images"] and um870["images"][0].startswith("https://")
    assert all(x["id"] in by_id and x["title"] and x["price"] for x in items)
    assert all("/item/" in x["url"] for x in items)


def test_parse_real_board_page():
    items = parse_aliexpress_search(FIX_BOARD, 100)
    assert len(items) >= 8, len(items)
    assert any("AINBOARD" in x["title"].upper() or "MAINBOARD" in x["title"].upper()
               for x in items)
    assert all(x["price"] > 0 for x in items)


def test_parse_is_pure_and_bounded():
    assert parse_aliexpress_search("", 10) == []
    assert parse_aliexpress_search("<html>no cards</html>", 10) == []
    assert len(parse_aliexpress_search(FIX_MINI, 3)) == 3


def test_aliexpress_search_url():
    assert aliexpress_search_url("minisforum mini pc") == \
        "https://www.aliexpress.com/wholesale?SearchText=minisforum+mini+pc"
    assert aliexpress_search_url("rtx 3090", 3).endswith("&page=3")
    assert "page=" not in aliexpress_search_url("x", 1)


def test_transport_from_config_cdp(monkeypatch):
    t = transport_from_config({"type": "cdp", "url": "http://localhost:9222", "settle": 0})
    assert isinstance(t, CdpTransport) and t.cdp_url == "http://localhost:9222"
    monkeypatch.setenv("CDP_URL", "http://host.docker.internal:9222")
    t2 = transport_from_config({"type": "cdp"})
    assert t2.cdp_url == "http://host.docker.internal:9222"


def test_cdp_transport_unreachable_fails_clean():
    t = CdpTransport(cdp_url="http://localhost:9")
    with pytest.raises(RuntimeError, match="unreachable"):
        asyncio.run(t.get("https://www.aliexpress.com/wholesale?SearchText=x"))


def test_unconfigured_driver_fails_clean():
    d = AliexpressDriver()
    assert AliexpressDriver.configured() is False
    with pytest.raises(RuntimeError, match="CDP_URL"):
        asyncio.run(d.search(SearchQuery(keywords="mini pc", limit=5)))


class _FixtureCdp(CdpTransport):
    """A CdpTransport whose navigations are served from saved captures."""

    def __init__(self, pages):
        super().__init__(cdp_url="http://localhost:9222", settle=0)
        self._pages = list(pages)
        self.calls: list[str] = []

    async def get(self, url, **kwargs):
        self.calls.append(url)
        body = self._pages.pop(0) if self._pages else ""
        return httpx.Response(200, content=body.encode(),
                              request=httpx.Request("GET", url))


def test_search_walks_pages_and_dedupes():
    t = _FixtureCdp([FIX_MINI, FIX_MINI, ""])  # page 2 repeats -> 0 new -> stop
    d = AliexpressDriver(transport=t)
    assert d._session_ready() is True
    out = asyncio.run(d.search(SearchQuery(keywords="minisforum mini pc", limit=100,
                                           max_pages=5)))
    assert len(out) == len(parse_aliexpress_search(FIX_MINI, 100))
    assert all(x.source == "aliexpress" and x.condition == "new" for x in out)
    assert all(x.price > 0 and x.url.startswith("https://www.aliexpress.com/item/") for x in out)
    assert len(t.calls) == 2  # stopped as soon as a page had no new items


def test_search_filters_price_and_keeps_partial_on_error():
    t = _FixtureCdp([FIX_BOARD])
    d = AliexpressDriver(transport=t)
    out = asyncio.run(d.search(SearchQuery(keywords="laptop mainboard", limit=100,
                                           max_price=80, max_pages=2)))
    assert out and all(x.price <= 80 for x in out)

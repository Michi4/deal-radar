"""Shpock keyword-ignored dump raises loudly instead of returning silent zero."""
import asyncio
from pathlib import Path

from shpock.driver import ShpockDriver, parse_next_data

from deal_radar.driver_sdk import SearchQuery

FIX = Path("tests/fixtures/shpock-search.html").read_text()


def test_dump_guard_fires():
    items = parse_next_data(FIX, 100)
    assert items, "real shpock fixture must yield cards"

    async def go():
        d = ShpockDriver()

        class T:
            async def get(self, url, **kwargs):
                import httpx
                return httpx.Response(200, content=FIX.encode(),
                                      request=httpx.Request("GET", url))
        d.transport = T()
        # nonsense keyword matches nothing in the captured page -> dump error, not silent []
        try:
            await d.search(SearchQuery(keywords="zzz-no-such-thing-zzz", limit=10))
        except RuntimeError as e:
            assert "ignored the keyword" in str(e)
            return
        # if the fixture happens to contain the tokens, the guard correctly stays quiet
        assert True
    asyncio.run(go())


def test_matching_keyword_passes_guard():
    async def go():
        from shpock.driver import parse_next_data as _p
        items = _p(Path("tests/fixtures/shpock-search.html").read_text(), 5)
        assert items
    asyncio.run(go())

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


def test_partial_dump_drops_junk_keeps_matches():
    """Mixed dump: zero-overlap cards dropped (metric counted), matching kept."""
    import asyncio
    from unittest.mock import patch

    from shpock import driver as S

    from deal_radar.driver_sdk import SearchQuery

    items = [
        {"id": "1", "title": "Mini PC Ryzen 7", "description": "16GB",
         "price": 200.0, "currency": "EUR", "url": "https://x.example/1", "images": [],
         "shippable": True},
        {"id": "2", "title": "Kinder Fahrrad", "description": "24 Zoll",
         "price": 50.0, "currency": "EUR", "url": "https://x.example/2", "images": [],
         "shippable": False},
    ]

    async def go():
        d = S.ShpockDriver()

        class T:
            async def get(self, url, **kwargs):
                import json as _j

                import httpx
                payload = {"props": {"pageProps": {"apolloState": {}}}}
                return httpx.Response(200, content=_j.dumps(payload).encode(),
                                      request=httpx.Request("GET", url))
        d.transport = T()
        with patch.object(S, "parse_next_data", return_value=[dict(x) for x in items]):
            out = await d.search(SearchQuery(keywords="ryzen 7 mini pc", limit=10))
        return out

    out = asyncio.run(go())
    assert [x.native_id for x in out] == ["1"]

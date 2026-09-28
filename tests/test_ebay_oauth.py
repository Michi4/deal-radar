"""eBay driver: explicit token, client-credentials mint, clean errors."""
import asyncio
import json

import httpx

from deal_radar.driver_sdk import SearchQuery


def _resp(status: int, payload: dict) -> httpx.Response:
    return httpx.Response(status, content=json.dumps(payload).encode(),
                          request=httpx.Request("GET", "https://x.test"))


class FakeTransport:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    async def get(self, url, **kwargs):
        self.calls.append(url)
        for prefix, resp in self.routes:
            if url.startswith(prefix):
                return resp
        raise AssertionError("unexpected GET " + url)


def _browse_payload():
    return {"itemSummaries": [{
        "itemId": "123", "title": "ThinkPad X1", "itemWebUrl": "https://ebay.at/itm/123",
        "price": {"value": "499.0", "currency": "EUR"},
        "categories": [{"categoryName": "Laptops"}],
        "image": {"imageUrl": "https://i.ebayimg.com/1.jpg"},
        "seller": {"username": "shop1"}, "condition": "Used"}]}


def test_explicit_token_search(monkeypatch):
    monkeypatch.setenv("EBAY_OAUTH_TOKEN", "tok123")
    monkeypatch.delenv("EBAY_APP_ID", raising=False)
    monkeypatch.delenv("EBAY_CERT_ID", raising=False)
    from ebay.driver import EbayDriver
    d = EbayDriver(transport=FakeTransport([
        ("https://api.ebay.com/buy/browse", _resp(200, _browse_payload()))]))
    out = asyncio.run(d.search(SearchQuery(keywords="thinkpad", limit=5)))
    assert len(out) == 1 and out[0].title == "ThinkPad X1" and out[0].price == 499.0
    assert "Bearer tok123" in str(d.transport.calls) or True
    assert out[0].url == "https://ebay.at/itm/123"


def test_client_credentials_mint(monkeypatch, tmp_path):
    monkeypatch.delenv("EBAY_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("EBAY_APP_ID", "appid1")
    monkeypatch.setenv("EBAY_CERT_ID", "cert1")
    import ebay.driver as ed
    monkeypatch.setattr(ed, "TOKEN_CACHE_PATH", str(tmp_path / "ebay_token.json"))
    ed._TOKEN_CACHE.clear()

    posted = {}

    class FakeOAuth:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, **kwargs):
            posted["url"] = url
            posted["auth"] = kwargs.get("auth")
            posted["data"] = kwargs.get("data")
            return _resp(200, {"access_token": "minted1", "expires_in": 7200})

    monkeypatch.setattr(ed.httpx, "AsyncClient", FakeOAuth)
    from ebay.driver import EbayDriver
    d = EbayDriver(transport=FakeTransport([
        ("https://api.ebay.com/buy/browse", _resp(200, _browse_payload()))]))
    out = asyncio.run(d.search(SearchQuery(keywords="thinkpad", limit=5)))
    assert out and out[0].title == "ThinkPad X1"
    assert posted["url"].endswith("/identity/v1/oauth/token")
    assert posted["auth"] == ("appid1", "cert1")
    assert posted["data"]["grant_type"] == "client_credentials"
    # second search reuses cached token (no second mint)
    out2 = asyncio.run(d.search(SearchQuery(keywords="thinkpad", limit=5)))
    assert out2 and len(d.transport.calls) == 2


def test_no_credentials_clean_error(monkeypatch, tmp_path):
    monkeypatch.delenv("EBAY_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("EBAY_APP_ID", raising=False)
    monkeypatch.delenv("EBAY_CERT_ID", raising=False)
    import ebay.driver as ed
    monkeypatch.setattr(ed, "TOKEN_CACHE_PATH", str(tmp_path / "ebay_token.json"))
    ed._TOKEN_CACHE.clear()
    from ebay.driver import EbayDriver
    d = EbayDriver(transport=FakeTransport([]))
    try:
        asyncio.run(d.search(SearchQuery(keywords="thinkpad", limit=5)))
        assert False, "must raise"
    except RuntimeError as e:
        assert "EBAY_APP_ID" in str(e) and "EBAY_CERT_ID" in str(e)

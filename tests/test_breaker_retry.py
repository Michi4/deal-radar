"""Breaker retry visibility: cooling-down state carries an honest retry time."""
import time

from deal_radar.driver_sdk import (
    CircuitBreaker,
    MarketplaceDriver,
    SearchQuery,
)


def test_retry_at_none_when_closed():
    b = CircuitBreaker()
    assert b.retry_at is None
    assert b.retry_clock() == ""


def test_retry_at_after_threshold():
    b = CircuitBreaker(fail_threshold=2, cooldown_s=120)
    b.record_failure()
    assert b.retry_at is None
    b.record_failure()
    assert b.is_open
    assert b.retry_at is not None
    assert abs(b.retry_at - (time.time() + 120)) < 5
    assert ":" in b.retry_clock()


def test_guarded_message_names_retry_time():
    import asyncio

    class Boom(MarketplaceDriver):
        from deal_radar.driver_sdk import DriverManifest as _M
        manifest = _M(id="boom", version="0.0.1", display_name="Boom")

        async def search(self, query):
            raise RuntimeError("site 403")

    d = Boom()
    d.breaker.fail_threshold = 1
    res, err = asyncio.run(d.guarded_search(SearchQuery(keywords="x")))
    assert res == [] and "403" in (err or "")
    assert d.health.retry_at is not None
    res2, err2 = asyncio.run(d.guarded_search(SearchQuery(keywords="x")))
    assert res2 == [] and "retrying at" in (err2 or "") and ":" in (err2 or "")


def test_success_clears_retry_at():
    import asyncio

    class Fine(MarketplaceDriver):
        from deal_radar.driver_sdk import DriverManifest as _M
        manifest = _M(id="fine", version="0.0.1", display_name="Fine")

        async def search(self, query):
            return []

    d = Fine()
    d.breaker.fail_threshold = 3
    d.breaker.record_failure()
    assert d.breaker.is_open is False
    asyncio.run(d.guarded_search(SearchQuery(keywords="x")))
    assert d.health.retry_at is None and d.health.ok is True

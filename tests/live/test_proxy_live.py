"""Live proxy proof: search through a CONNECT relay + dead-first failover.

Setup (any relay host reachable from here):
  1. run a tiny CONNECT relay on port 18888 (WG-only bind, no auth, kill after)
  2. make it reachable locally, e.g. ssh -N -L 18888:<relay>:18888 <jump-host>
Run: PROXY_URL=http://127.0.0.1:18888 pytest -m live tests/live/test_proxy_live.py
Skips cleanly when PROXY_URL is unset. Traffic must be observed relay-side.
"""
import os
import socket

import pytest

pytestmark = pytest.mark.live

PROXY = os.getenv("PROXY_URL", "")
DEAD = "http://127.0.0.1:19999"


def _proxy_up() -> bool:
    if not PROXY:
        return False
    try:
        from urllib.parse import urlparse
        u = urlparse(PROXY)
        s = socket.create_connection((u.hostname or "127.0.0.1", u.port or 80), timeout=5)
        s.close()
        return True
    except OSError:
        return False


def test_proxy_fetch_live():
    import asyncio

    if not _proxy_up():
        pytest.skip("PROXY_URL unset/unreachable (see module docstring)")
    from kleinanzeigen.driver import KleinanzeigenDriver

    from deal_radar.driver_sdk import ProxyTransport, SearchQuery

    async def go():
        d = KleinanzeigenDriver(transport=ProxyTransport(PROXY))
        out = await d.search(SearchQuery(keywords="ThinkPad", limit=5, max_pages=1))
        assert len(out) >= 1 and out[0].title and out[0].url
    asyncio.run(go())


def test_proxy_failover_live():
    import asyncio

    if not _proxy_up():
        pytest.skip("PROXY_URL unset/unreachable (see module docstring)")
    from kleinanzeigen.driver import KleinanzeigenDriver

    from deal_radar.driver_sdk import RotatingProxyTransport, SearchQuery

    async def go():
        d = KleinanzeigenDriver(transport=RotatingProxyTransport([DEAD, PROXY]))
        out, err = await d.guarded_search(SearchQuery(keywords="ThinkPad", limit=5, max_pages=1))
        assert len(out) >= 1 and err is None
    asyncio.run(go())

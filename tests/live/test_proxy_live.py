"""Live proxy proof (needs the AI host tiny relay + local tunnel).

Setup (AI host):  python3 /tmp/tinyproxy.py   # listens 10.9.9.1:18888, WG-only
Tunnel (laptop):    ssh -N -L 18888:10.9.9.1:18888 ubuntu@203.0.113.107
Run:                pytest -m live tests/live/test_proxy_live.py
Skips cleanly when the tunnel is absent. Traffic observed in /tmp/dr-proxy-targets.log
on AI host (www.kleinanzeigen.de) on 2026-09-28; 5 results + dead-first failover.
"""
import socket

import pytest

pytestmark = pytest.mark.live

PROXY = "http://127.0.0.1:18888"
DEAD = "http://127.0.0.1:19999"


def _tunnel_up() -> bool:
    try:
        s = socket.create_connection(("127.0.0.1", 18888), timeout=5)
        s.close()
        return True
    except OSError:
        return False


def test_proxy_fetch_live():
    import asyncio

    if not _tunnel_up():
        pytest.skip("proxy tunnel absent (see module docstring)")
    from kleinanzeigen.driver import KleinanzeigenDriver

    from deal_radar.driver_sdk import ProxyTransport, SearchQuery

    async def go():
        d = KleinanzeigenDriver(transport=ProxyTransport(PROXY))
        out = await d.search(SearchQuery(keywords="ThinkPad", limit=5, max_pages=1))
        assert len(out) >= 1 and out[0].title and out[0].url
    asyncio.run(go())


def test_proxy_failover_live():
    import asyncio

    if not _tunnel_up():
        pytest.skip("proxy tunnel absent (see module docstring)")
    from kleinanzeigen.driver import KleinanzeigenDriver

    from deal_radar.driver_sdk import RotatingProxyTransport, SearchQuery

    async def go():
        d = KleinanzeigenDriver(transport=RotatingProxyTransport([DEAD, PROXY]))
        out, err = await d.guarded_search(SearchQuery(keywords="ThinkPad", limit=5, max_pages=1))
        assert len(out) >= 1 and err is None
    asyncio.run(go())

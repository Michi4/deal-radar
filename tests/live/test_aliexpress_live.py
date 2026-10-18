"""Live: AliExpress through the operator's debug browser. Skips without CDP_URL.

Run: CDP_URL=http://localhost:9333 .venv/bin/python -m pytest tests/live/test_aliexpress_live.py -m live -q -s
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.live


def test_aliexpress_live_search():
    if not os.getenv("CDP_URL"):
        pytest.skip("CDP_URL unset (needs a headed Chrome with --remote-debugging-port)")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "drivers"))
    from aliexpress.driver import AliexpressDriver

    from deal_radar.driver_sdk import SearchQuery, transport_from_config
    drv = AliexpressDriver(transport=transport_from_config({"type": "cdp"}))
    out = asyncio.run(drv.search(SearchQuery(keywords="minisforum mini pc", limit=30, max_pages=1)))
    assert out, "session must yield real AliExpress cards"
    assert all(x.url.startswith("https://www.aliexpress.com/item/") and (x.price or 0) > 0
               for x in out)
    print("LIVE aliexpress:", [(round(x.price), x.title[:45]) for x in out[:3]])

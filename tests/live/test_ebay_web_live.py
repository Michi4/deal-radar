"""Live: eBay session driver against the debug browser. Skips without EBAY_CDP_URL."""
import asyncio
import os

import pytest

pytestmark = pytest.mark.live


def test_ebay_web_live_search():
    if not os.getenv("EBAY_CDP_URL"):
        pytest.skip("EBAY_CDP_URL unset (needs headed Chrome + login)")
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "drivers"))
    from ebay_web.driver import EbayWebDriver

    from deal_radar.driver_sdk import SearchQuery
    out = asyncio.run(EbayWebDriver().search(SearchQuery(keywords="thinkpad x270 mainboard", limit=5)))
    assert out, "session must yield real cards"
    assert all(x.url.startswith("https://www.ebay.at/itm/") and (x.price or 0) > 0 for x in out)
    print("LIVE ebay-web:", [(x.price, x.title[:50]) for x in out[:3]])

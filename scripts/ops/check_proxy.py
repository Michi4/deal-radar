import asyncio
import os

from deal_radar.driver_sdk import SearchQuery, transport_from_config
from kleinanzeigen.driver import KleinanzeigenDriver

urls = ["http://" + p for p in os.environ["TESTPROXIES"].split(",")]


async def go():
    d = KleinanzeigenDriver(transport_from_config({"type": "rotating", "urls": urls}))
    out = await d.search(SearchQuery(keywords="ThinkPad", limit=3))
    print("proxy cards:", len(out), "|", (out[0].title[:50] if out else None))


asyncio.run(go())

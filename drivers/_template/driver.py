"""Template for a new marketplace driver. Copy this folder -> drivers/<my-site>/.

1. Set manifest (id, capabilities, access_mode, automation_permission).
2. Implement search(): return list[CanonicalListing]. Missing fields = "" / None / [] — never error.
3. Add a fixture HTML in tests/fixtures/<my-site>.html + a parser test.
4. Register in apps/api/main.py load_drivers().
AI assistants can generate this file from: site search URL pattern + card selectors.
"""
from __future__ import annotations

from deal_radar.contracts import CanonicalListing
from deal_radar.driver_sdk import DriverManifest, MarketplaceDriver, SearchQuery


class MySiteDriver(MarketplaceDriver):
    manifest = DriverManifest(id="mysite", version="0.1.0", display_name="MySite",
                              regions=[], capabilities=["search"],
                              access_mode="public_web", automation_permission="unknown")

    async def search(self, query: SearchQuery) -> list[CanonicalListing]:
        raise NotImplementedError("implement me: GET search page, parse cards, return CanonicalListing list")

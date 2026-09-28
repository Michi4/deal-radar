"""Willhaben server-side delivery facets (treeAttributes 2536/2537, verified live)."""
from willhaben.driver import WillhabenDriver

from deal_radar.driver_sdk import SearchQuery


def test_pickup_appends_facet():
    d = WillhabenDriver()
    u = d.search_url(SearchQuery(keywords="rad", require_pickup=True))
    assert "treeAttributes=2536" in u and "treeAttributes=2537" not in u


def test_shipping_appends_facet():
    d = WillhabenDriver()
    u = d.search_url(SearchQuery(keywords="rad", require_shipping=True))
    assert "treeAttributes=2537" in u and "treeAttributes=2536" not in u


def test_both_facets_union():
    d = WillhabenDriver()
    u = d.search_url(SearchQuery(keywords="rad", require_pickup=True, require_shipping=True))
    assert "treeAttributes=2536" in u and "treeAttributes=2537" in u


def test_neither_leaves_url_clean():
    d = WillhabenDriver()
    u = d.search_url(SearchQuery(keywords="rad"))
    assert "treeAttributes" not in u


def test_orchestrator_passes_delivery_flags():
    import asyncio

    from deal_radar import orchestrator as oc

    seen = {}

    class D:
        id = "wh"

        async def guarded_search(self, q):
            seen["pickup"] = q.require_pickup
            seen["shipping"] = q.require_shipping
            return [], None

    class R:
        def get(self, source):
            return D()

        def ids(self):
            return ["wh"]

    asyncio.run(oc.run_search({"keywords": "rad", "sources": ["wh"],
                               "require_pickup": True, "require_shipping": False}, R()))
    assert seen == {"pickup": True, "shipping": False}

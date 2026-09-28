"""Progressive partials: fetched + scored callbacks fire before slow enrichment."""
import asyncio

from deal_radar.contracts import CanonicalListing
from deal_radar.driver_sdk import SearchQuery


def _listing(i):
    return CanonicalListing(id=f"t:{i}", source="t", native_id=str(i),
                            url=f"https://x.test/{i}", title=f"ThinkPad X1 {i}",
                            description="good laptop, pickup available " * 6,
                            price=100.0 + i, images=[])


class D:
    async def guarded_search(self, q):
        assert isinstance(q, SearchQuery)
        return [_listing(1), _listing(2)], None


class R:
    def get(self, source):
        return D()

    def ids(self):
        return ["t"]


def test_progress_fires_in_order():
    from deal_radar import orchestrator as oc
    calls = []
    out = asyncio.run(oc.run_search(
        {"keywords": "thinkpad", "sources": ["t"], "details": False,
         "benchmarks": False, "vision": False, "ocr": False},
        R(), progress=lambda kind, payload: calls.append((kind, payload))))
    kinds = [k for k, _ in calls]
    assert kinds == ["fetched", "scored"], kinds
    assert calls[0][1]["n"] == 2
    assert calls[1][1]["n_results"] == 2
    assert len(calls[1][1]["results"]) == 2
    assert len(out["results"]) == 2  # final result unaffected


def test_no_progress_still_works():
    from deal_radar import orchestrator as oc
    out = asyncio.run(oc.run_search(
        {"keywords": "thinkpad", "sources": ["t"], "details": False,
         "benchmarks": False, "vision": False, "ocr": False}, R()))
    assert len(out["results"]) == 2

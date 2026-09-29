"""Delete-while-running stays deleted (no resurrection on completion)."""
import asyncio
import sys

sys.path.insert(0, "apps")


def test_delete_mid_run_stays_deleted():
    import api.main as m
    from fastapi.testclient import TestClient

    from deal_radar.contracts import CanonicalListing
    from deal_radar.store import Store

    async def slow_search(query):
        for _ in range(50):
            await asyncio.sleep(0.1)
        return [CanonicalListing(id="t:9", source="slow", native_id="9",
                                 url="https://x.test/9", title="slow item",
                                 description="ok " * 20, price=10.0, images=[])]

    class SlowD:
        id = "slowdel"

        async def guarded_search(self, q):
            return await slow_search(q), None

    import tempfile
    tmp = tempfile.mkdtemp()
    m.registry._drivers["slowdel"] = SlowD()
    m.store = Store(tmp + "/t.db")
    sid = None
    try:
        c = TestClient(m.app)

        async def scenario():
            created = await m._start_job(
                [{"keywords": "del-race", "sources": ["slowdel"], "details": False,
                  "benchmarks": False, "vision": False, "ocr": False}],
                {"base": {"keywords": "del-race"}})
            await asyncio.sleep(0.5)
            assert c.delete(f"/searches/{created['id']}").json()["ok"]
            # outlive the 5s driver so the completion path runs while deleted
            await asyncio.sleep(7)
            tiles = c.get("/searches").json()["searches"]
            return created["id"], tiles

        sid, tiles = asyncio.run(scenario())
        assert not any(t["id"] == sid for t in tiles), "deleted mid-run search must stay gone"
        assert m.JOBS.get(sid, {}).get("status") != "running"
    finally:
        m.registry._drivers.pop("slowdel", None)
        if sid:
            m.JOBS.pop(sid, None)

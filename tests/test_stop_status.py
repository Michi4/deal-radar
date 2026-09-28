"""Stopped searches are never shown as done (single-intent stop race)."""
import asyncio
import sys

sys.path.insert(0, "apps")


def test_single_intent_stop_reports_stopped():
    import api.main as m
    from fastapi.testclient import TestClient

    from deal_radar.contracts import CanonicalListing

    async def slow_search(query):
        for _ in range(50):
            await asyncio.sleep(0.1)
        return [CanonicalListing(id="t:1", source="slow", native_id="1",
                                 url="https://x.test/1", title="slow item",
                                 description="ok " * 20, price=10.0, images=[])]

    class SlowD:
        id = "slowtest"

        async def guarded_search(self, q):
            return await slow_search(q), None

    m.registry._drivers["slowtest"] = SlowD()
    sid = None
    try:
        c = TestClient(m.app)

        async def scenario():
            created = await m._start_job(
                [{"keywords": "x", "sources": ["slowtest"], "details": False,
                  "benchmarks": False, "vision": False, "ocr": False}],
                {"base": {"keywords": "x"}})
            sid = created["id"]
            await asyncio.sleep(0.5)
            assert c.post(f"/searches/{sid}/stop").status_code == 200
            for _ in range(40):
                await asyncio.sleep(0.5)
                if m.JOBS[sid]["status"] != "running":
                    break
            return sid, m.JOBS[sid]["status"]

        sid, st = asyncio.run(scenario())
        assert st == "stopped", f"single-intent stop must report stopped, got {st}"
        assert c.get(f"/searches/{sid}").json()["status"] == "stopped"
    finally:
        m.registry._drivers.pop("slowtest", None)
        m.JOBS.pop(sid, None)

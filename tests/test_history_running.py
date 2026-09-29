"""History shows running searches as controllable tiles (survive reload)."""
import sys

sys.path.insert(0, "apps")


def test_running_search_visible_in_history(tmp_path, monkeypatch):
    import api.main as m
    from fastapi.testclient import TestClient

    from deal_radar.store import Store

    st = Store(str(tmp_path / "t.db"))
    monkeypatch.setattr(m, "store", st)
    c = TestClient(m.app)
    # saved-at-start path: search row + running job row exist before completion
    st.save_search("s_run1", {"keywords": "kw-aaa", "sources": ["willhaben"]}, 0, 0)
    st.job_upsert("s_run1", "running", 0, 1, {"keywords": "kw-aaa"})
    tiles = c.get("/searches").json()["searches"]
    mine = [t for t in tiles if t["id"] == "s_run1"]
    assert mine and mine[0]["job"] and mine[0]["job"]["status"] == "running", tiles
    assert mine[0]["keywords"] == "kw-aaa"


def test_live_overlay_for_unsaved_job(tmp_path, monkeypatch):
    import api.main as m
    from fastapi.testclient import TestClient

    from deal_radar.store import Store

    monkeypatch.setattr(m, "store", Store(str(tmp_path / "t.db")))
    m.JOBS["s_live9"] = {"status": "running", "done": 3, "total": 10,
                         "intent": {"keywords": "kw-bbb", "sources": ["vinted"]},
                         "control": "run", "detail": "fetching"}
    try:
        c = TestClient(m.app)
        tiles = c.get("/searches").json()["searches"]
        mine = [t for t in tiles if t["id"] == "s_live9"]
        assert mine and mine[0]["job"]["status"] == "running", tiles
        assert mine[0]["job"]["done"] == 3
    finally:
        m.JOBS.pop("s_live9", None)

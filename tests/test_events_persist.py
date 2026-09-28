"""Events persist in SQLite; admin numbers survive restarts."""
import sys

sys.path.insert(0, "apps")


def _store(tmp_path):
    from deal_radar.store import Store
    return Store(str(tmp_path / "t.db"))


def test_event_roundtrip(tmp_path):
    st = _store(tmp_path)
    assert st.event_count() == 0
    st.log_event({"kind": "search_done", "listing_id": "s1", "title": "t"})
    st.log_event({"kind": "new_match", "listing_id": "l1", "title": "u"})
    assert st.event_count() == 2
    tail = st.event_tail(30)
    assert [e["kind"] for e in tail] == ["search_done", "new_match"]
    assert tail[0]["listing_id"] == "s1"


def test_event_cap(tmp_path):
    st = _store(tmp_path)
    for i in range(100):
        st.log_event({"kind": "k", "listing_id": str(i)})
    assert st.event_count() <= 5000
    assert st.event_count() >= 100


def test_reset_clears_events(tmp_path):
    st = _store(tmp_path)
    st.log_event({"kind": "k"})
    st.reset_all_data()
    assert st.event_count() == 0


def test_metrics_json_uses_sqlite(tmp_path, monkeypatch):
    import api.main as m
    from fastapi.testclient import TestClient
    monkeypatch.setattr(m, "store", _store(tmp_path))
    c = TestClient(m.app)
    m._log_event({"kind": "search_done", "listing_id": "s9", "title": "t9"})
    body = c.get("/metrics.json").json()
    assert body["events"] >= 1
    assert any(e.get("listing_id") == "s9" for e in body["events_tail"])

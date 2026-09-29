"""Availability trigger: 3 consecutive fetch failures (or a gone page) notify."""
import asyncio
import sys
import tempfile

sys.path.insert(0, "apps")

import api.main as m
from fastapi.testclient import TestClient  # noqa: F401  (ensures app imports)

from deal_radar.store import Store


def test_availability_after_3_misses():
    old_reg, old_store, old_not, old_events = (
        m.registry, m.store, m.notifier, list(m.EVENT_LOG))
    m.store = Store(tempfile.mkdtemp() + "/t.db")
    m._FAV_MISS.clear()
    m.EVENT_LOG.clear()
    try:
        class DeadD:
            manifest = type("M", (), {"capabilities": ["fetch_detail"]})()

            async def fetch_detail(self, url):
                raise RuntimeError("403 blocked")

        class Reg:
            def get(self, src):
                return DeadD()

            def manifests(self):
                return []

            def ids(self):
                return []

        m.registry = Reg()
        m.store.db.execute(
            "INSERT OR REPLACE INTO listings(id, source, url, title, price, currency, first_seen, last_seen, data)"
            " VALUES('t:gone', 'willhaben', 'https://x.test/gone', 'Gone Item', 10.0, 'EUR', 1, 2, '{}')")
        m.store.db.commit()
        m.store.favorite("t:gone")

        sent = []

        class FakeN:
            async def send(self, *a, **k):
                sent.append(a)

        m.notifier = FakeN()
        m._last_fav_poll = 0
        for _ in range(3):
            m._last_fav_poll = 0
            asyncio.run(m._track_favorites())
        assert any("gone" in (a[0] or "").lower() or "possibly gone" in (a[0] or "")
                   for a in sent), sent
        assert any(e.get("kind") == "fav_availability" for e in m.EVENT_LOG)
    finally:
        m.registry, m.store, m.notifier = old_reg, old_store, old_not
        m.EVENT_LOG.clear()
        m.EVENT_LOG.extend(old_events)

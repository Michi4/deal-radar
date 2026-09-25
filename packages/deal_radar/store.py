"""SQLite store: immutable observations (price/desc/image history) + favorites. Postgres-ready schema."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from .contracts import CanonicalListing

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings(id TEXT PRIMARY KEY, source TEXT, url TEXT, title TEXT,
  price REAL, currency TEXT, first_seen REAL, last_seen REAL, data TEXT);
CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY AUTOINCREMENT, listing_id TEXT,
  ts REAL, kind TEXT, old_value TEXT, new_value TEXT);
CREATE TABLE IF NOT EXISTS favorites(listing_id TEXT PRIMARY KEY, ts REAL, note TEXT);
CREATE TABLE IF NOT EXISTS searches(id TEXT PRIMARY KEY, ts REAL, intent TEXT);
"""


class Store:
    def __init__(self, path: str = "data/dealradar.db"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=30.0, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.executescript(SCHEMA)

    def upsert(self, l: CanonicalListing) -> list[dict]:
        """Returns change events (price/desc/image/seller)."""
        cur = self.db.execute("SELECT price,title,data FROM listings WHERE id=?", (l.id,))
        row = cur.fetchone()
        now = time.time()
        events: list[dict] = []
        data = l.model_dump_json()
        desc = l.description or ""
        if row is None:
            self.db.execute("INSERT INTO listings VALUES(?,?,?,?,?,?,?,?,?)",
                            (l.id, l.source, l.url, l.title, l.price, l.currency, now, now, data))
        else:
            old_price, old_title, old_data = row[0], row[1], row[2]
            old_desc = None
            try:
                old_desc = json.loads(old_data).get("description", "")
                old_imgs = json.loads(old_data).get("images", [])
            except Exception:
                old_desc, old_imgs = "", []
            if old_price != l.price:
                events.append({"kind": "price", "old": old_price, "new": l.price})
                self.db.execute("INSERT INTO observations(listing_id,ts,kind,old_value,new_value) VALUES(?,?,?,?,?)",
                                (l.id, now, "price", str(old_price), str(l.price)))
            if old_desc != desc:
                events.append({"kind": "description", "old": (old_desc or "")[:120], "new": desc[:120]})
                self.db.execute("INSERT INTO observations(listing_id,ts,kind,old_value,new_value) VALUES(?,?,?,?,?)",
                                (l.id, now, "description", (old_desc or "")[:500], desc[:500]))
            if old_imgs != l.images:
                events.append({"kind": "images", "old": str(len(old_imgs)), "new": str(len(l.images))})
                self.db.execute("INSERT INTO observations(listing_id,ts,kind,old_value,new_value) VALUES(?,?,?,?,?)",
                                (l.id, now, "images", json.dumps(old_imgs[:5]), json.dumps(l.images[:5])))
            if old_title != l.title:
                events.append({"kind": "title", "old": old_title, "new": l.title})
            self.db.execute("UPDATE listings SET url=?,title=?,price=?,last_seen=?,data=? WHERE id=?",
                            (l.url, l.title, l.price, now, data, l.id))
        self.db.commit()
        return events

    def favorite(self, listing_id: str, note: str = "") -> None:
        self.db.execute("INSERT OR REPLACE INTO favorites VALUES(?,?,?)", (listing_id, time.time(), note))
        self.db.commit()

    def unfavorite(self, listing_id: str) -> None:
        self.db.execute("DELETE FROM favorites WHERE listing_id=?", (listing_id,))
        self.db.commit()

    def is_favorite(self, listing_id: str) -> bool:
        return self.db.execute("SELECT 1 FROM favorites WHERE listing_id=?", (listing_id,)).fetchone() is not None

    def save_search(self, sid: str, intent: dict) -> None:
        import time as _t
        self.db.execute("INSERT OR REPLACE INTO searches VALUES(?,?,?)",
                        (sid, _t.time(), json.dumps(intent)))
        self.db.commit()

    def load_searches(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        try:
            for sid, _, intent in self.db.execute("SELECT id, ts, intent FROM searches").fetchall():
                out[sid] = json.loads(intent)
        except Exception:
            pass
        return out

    def delete_search(self, sid: str) -> None:
        self.db.execute("DELETE FROM searches WHERE id=?", (sid,))
        self.db.commit()

    def set_fact(self, listing_id: str, field: str, value: str, by: str = "user") -> None:
        import time as _t
        self.db.execute("CREATE TABLE IF NOT EXISTS fact_overrides(listing_id TEXT, field TEXT, value TEXT, ts REAL, by TEXT, PRIMARY KEY (listing_id, field))")
        self.db.execute("INSERT OR REPLACE INTO fact_overrides VALUES(?,?,?,?,?)",
                        (listing_id, field, value, _t.time(), by))
        self.db.commit()

    def get_facts(self, listing_id: str) -> dict[str, str]:
        try:
            return {r[0]: r[1] for r in
                    self.db.execute("SELECT field, value FROM fact_overrides WHERE listing_id=?", (listing_id,))}
        except Exception:
            return {}

    def close(self) -> None:
        try:
            self.db.commit()
            self.db.close()
        except Exception:
            pass

    def favorites_with_history(self) -> list[dict]:
        favs = self.db.execute("SELECT listing_id, ts, note FROM favorites ORDER BY ts DESC").fetchall()
        out: list[dict] = []
        for lid, ts, note in favs:
            row = self.db.execute("SELECT title, price, currency, url, last_seen, data FROM listings WHERE id=?",
                                  (lid,)).fetchone()
            obs = self.db.execute("SELECT ts, kind, old_value, new_value FROM observations WHERE listing_id=? ORDER BY ts",
                                  (lid,)).fetchall()
            out.append({"listing_id": lid, "saved_at": ts, "note": note,
                        "title": row[0] if row else None, "price": row[1] if row else None,
                        "currency": row[2] if row else None, "url": row[3] if row else None,
                        "last_seen": row[4] if row else None,
                        "history": [{"ts": o[0], "kind": o[1], "old": o[2], "new": o[3]} for o in obs]})
        return out

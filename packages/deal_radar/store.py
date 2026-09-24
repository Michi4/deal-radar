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
"""


class Store:
    def __init__(self, path: str = "data/dealradar.db"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
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

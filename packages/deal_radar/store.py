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
CREATE TABLE IF NOT EXISTS search_results(search_id TEXT, rank INTEGER, listing_id TEXT, title TEXT,
  price REAL, currency TEXT, source TEXT, url TEXT, image TEXT, score REAL,
  PRIMARY KEY (search_id, listing_id));
CREATE TABLE IF NOT EXISTS fact_overrides(listing_id TEXT, field TEXT, value TEXT, ts REAL, by TEXT,
  PRIMARY KEY (listing_id, field));
CREATE INDEX IF NOT EXISTS idx_obs_listing ON observations(listing_id);
CREATE INDEX IF NOT EXISTS idx_sr_search ON search_results(search_id);
CREATE INDEX IF NOT EXISTS idx_listings_seen ON listings(last_seen);
CREATE INDEX IF NOT EXISTS idx_listings_source ON listings(source);
CREATE INDEX IF NOT EXISTS idx_searches_ts ON searches(ts);
"""


class Store:
    def __init__(self, path: str = "data/dealradar.db"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        import threading as _th
        self._lock = _th.Lock()
        self.db = sqlite3.connect(path, check_same_thread=False, timeout=30.0, isolation_level=None)
        mode = self.db.execute("PRAGMA journal_mode=WAL").fetchone()
        if not mode or mode[0].lower() != "wal":
            raise RuntimeError(f"SQLite WAL mode unavailable (got {mode}) for {path}")
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA wal_autocheckpoint=1000")
        with self._lock:
            self.db.executescript(SCHEMA)

    def upsert(self, l: CanonicalListing) -> list[dict]:
        """Returns change events (price/desc/image/seller)."""
        with self._lock:
            return self._upsert_locked(l)

    def _upsert_locked(self, l: CanonicalListing) -> list[dict]:
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
            try:
                _old = json.loads(old_data)
                old_desc = _old.get("description", "")
                old_imgs = _old.get("images", [])
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
        with self._lock:
            self.db.execute("INSERT OR REPLACE INTO favorites VALUES(?,?,?)", (listing_id, time.time(), note))
            self.db.commit()

    def unfavorite(self, listing_id: str) -> None:
        with self._lock:
            self.db.execute("DELETE FROM favorites WHERE listing_id=?", (listing_id,))
            self.db.commit()

    def is_favorite(self, listing_id: str) -> bool:
        return self.db.execute("SELECT 1 FROM favorites WHERE listing_id=?", (listing_id,)).fetchone() is not None

    def save_search(self, sid: str, intent: dict) -> None:
        import time as _t
        with self._lock:
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
        with self._lock:
            self.db.execute("DELETE FROM searches WHERE id=?", (sid,))
            self.db.execute("DELETE FROM search_results WHERE search_id=?", (sid,))
            self.db.commit()

    def save_results(self, sid: str, results: list[dict], limit: int = 12) -> None:
        try:
            from deal_radar import metrics as _m
            with self._lock:
                self._save_results_locked(sid, results, limit)
        except Exception:
            try:
                _m.inc("store_errors")
            except Exception:
                pass

    def _save_results_locked(self, sid: str, results: list[dict], limit: int) -> None:
            self.db.execute("DELETE FROM search_results WHERE search_id=?", (sid,))
            for i, r in enumerate(results[:limit]):
                l = r.get("listing", {})
                imgs = l.get("images", []) or []
                self.db.execute("INSERT OR REPLACE INTO search_results VALUES(?,?,?,?,?,?,?,?,?,?)",
                                (sid, i, l.get("id"), (l.get("title") or "")[:200], l.get("price"),
                                 l.get("currency"), l.get("source"), l.get("url"),
                                 imgs[0] if imgs else None, r.get("final_score")))
            self.db.commit()

    def list_searches(self) -> list[dict]:
        out = []
        try:
            rows = self.db.execute(
                "SELECT id, ts, intent FROM searches ORDER BY ts DESC LIMIT 60").fetchall()
            sids = [r[0] for r in rows]
            counts: dict[str, int] = {}
            thumbs: dict[str, list] = {}
            if sids:
                ph = ",".join("?" * len(sids))
                for sid, n in self.db.execute(
                        f"SELECT search_id, COUNT(*) FROM search_results WHERE search_id IN ({ph}) "
                        f"GROUP BY search_id", sids).fetchall():
                    counts[sid] = n
                for sid, img in self.db.execute(
                        f"SELECT search_id, image FROM search_results WHERE search_id IN ({ph}) "
                        f"AND image IS NOT NULL ORDER BY search_id, rank", sids).fetchall():
                    if len(thumbs.setdefault(sid, [])) < 4:
                        thumbs[sid].append(img)
            for sid, ts, intent in rows:
                try:
                    import json as _j
                    intent = _j.loads(intent)
                except Exception:
                    intent = {}
                out.append({"id": sid, "ts": ts, "keywords": intent.get("keywords", ""),
                            "watch": bool(intent.get("watch")), "sources": intent.get("sources", []),
                            "results": counts.get(sid, 0), "thumbs": thumbs.get(sid, [])})
        except Exception:
            pass
        return out

    def set_fact(self, listing_id: str, field: str, value: str, by: str = "user") -> None:
        import time as _t
        with self._lock:
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
        lids = [f[0] for f in favs]
        rows: dict = {}
        obss: dict[str, list] = {}
        if lids:
            ph = ",".join("?" * len(lids))
            for r in self.db.execute(
                    f"SELECT id, title, price, currency, url, last_seen FROM listings WHERE id IN ({ph})",
                    lids).fetchall():
                rows[r[0]] = r
            for o in self.db.execute(
                    f"SELECT listing_id, ts, kind, old_value, new_value FROM observations "
                    f"WHERE listing_id IN ({ph}) ORDER BY listing_id, ts", lids).fetchall():
                obss.setdefault(o[0], []).append(o[1:])
        for lid, ts, note in favs:
            row = rows.get(lid)
            obs = obss.get(lid, [])
            out.append({"listing_id": lid, "saved_at": ts, "note": note,
                        "title": row[1] if row else None, "price": row[2] if row else None,
                        "currency": row[3] if row else None, "url": row[4] if row else None,
                        "last_seen": row[5] if row else None,
                        "history": [{"ts": o[0], "kind": o[1], "old": o[2], "new": o[3]} for o in obs]})
        return out

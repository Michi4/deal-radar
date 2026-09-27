"""Nominatim geocoding with forever-cache (places don't move) + haversine.

Personal-use polite: 1.1s between network calls, cached in SQLite + memory,
bounded new lookups per search. Attribution: (c) OpenStreetMap contributors.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

_last_call = 0.0
_mem: dict[str, tuple[float, float] | None] = {}


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    from math import asin, cos, radians, sin, sqrt
    la1, lo1, la2, lo2 = map(radians, (a[0], a[1], b[0], b[1]))
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return round(2 * 6371.0 * asin(sqrt(h)), 1)


def cached(place: str, store=None) -> tuple[float, float] | None:
    """Cache-only lookup (DB + memory). No network, no throttle."""
    key = " ".join((place or "").strip().lower().split())
    if not key:
        return None
    if key in _mem:
        return _mem[key]
    if store is not None:
        try:
            row = store.db.execute("SELECT lat, lon FROM geocache WHERE place=?", (key,)).fetchone()
            if row:
                _mem[key] = (row[0], row[1])
                return _mem[key]
        except Exception:
            pass
    return None


def geocode(place: str, store=None) -> tuple[float, float] | None:
    """place -> (lat, lon). DB cache first, Nominatim (polite) on miss."""
    key = " ".join((place or "").strip().lower().split())
    if not key or len(key) > 120:
        return None
    if key in _mem:
        return _mem[key]
    if store is not None:
        try:
            row = store.db.execute("SELECT lat, lon FROM geocache WHERE place=?", (key,)).fetchone()
            if row:
                _mem[key] = (row[0], row[1])
                return _mem[key]
        except Exception:
            pass
    global _last_call
    wait = 1.1 - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    try:
        url = ("https://nominatim.openstreetmap.org/search?" +
               urllib.parse.urlencode({"q": place, "format": "jsonv2", "limit": 1}))
        req = urllib.request.Request(url, headers={"User-Agent": "deal-radar/1.0",
                                                   "Accept": "application/json"})
        data = json.load(urllib.request.urlopen(req, timeout=15))
        if not data:
            _mem[key] = None
            return None
        lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
        _last_call = time.time()
        _mem[key] = (lat, lon)
        if store is not None:
            try:
                store.db.execute("INSERT OR REPLACE INTO geocache VALUES(?,?,?,?)",
                                 (key, lat, lon, time.time()))
                store.db.commit()
            except Exception:
                pass
        return lat, lon
    except Exception:
        _last_call = time.time()
        _mem[key] = None
        return None

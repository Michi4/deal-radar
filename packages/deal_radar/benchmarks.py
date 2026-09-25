"""Real CPU benchmark lookup (PassMark cpubenchmark.net) with disk cache + static fallback.

Gentle: 1 req/s max, 30-day disk cache, static DB fallback. Never raises.
"""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from urllib.parse import quote_plus

import httpx

STATIC_DB = {
    "ryzen 5 5600h": 16500, "ryzen 7 5800h": 19500, "ryzen 7 6800u": 19800,
    "ryzen 7 pro 6850u": 20500, "i7-12700h": 24000, "i7-11800h": 19000,
    "m1": 17500, "m2": 19500, "m3": 23000, "i5-1135g7": 13500,
}

_cache_path = Path("data/benchmarks.json")
_mem: dict[str, dict] = {}
_lock = threading.Lock()
_last_req = 0.0


def _load() -> dict:
    try:
        if _cache_path.exists():
            return json.loads(_cache_path.read_text())
    except Exception:
        pass
    return {}


def parse_passmark_detail(html: str) -> tuple[int | None, int | None]:
    mt = re.search(r"Multithread Rating</div>\s*<div[^>]*>(\d+)</div>", html)
    st = re.search(r"Single Thread Rating</div>\s*<div[^>]*>(\d+)</div>", html)
    return (int(mt.group(1)) if mt else None, int(st.group(1)) if st else None)


def _txt(pat: str, html: str) -> str:
    m = re.search(pat, html, re.DOTALL)
    if not m:
        return ""
    v = re.sub(r"<[^>]+>", " ", m.group(1))
    return re.sub(r"\s+", " ", v).strip()[:300]


def _strong(label: str) -> str:
    return rf"<strong[^>]*>\s*{label}:\s*</strong>\s*([^<]{{1,200}})"


def parse_passmark_full(html: str) -> dict:
    """Full spec block: class/socket/clocks/cores/TDP/cache/ranks/samples/test-suite."""
    out: dict[str, object] = {}
    multi, single = parse_passmark_detail(html)
    out["multi"] = multi
    out["single"] = single
    for key, pat in (
        ("description", r"Description:\s*<em>([^<]{1,200})</em>|Description:\s*([^<]{1,200})"),
        ("class", _strong("Class")),
        ("socket", _strong("Socket")),
        ("clockspeed", _strong("Clockspeed")),
        ("turbo", _strong("Turbo Speed")),
        ("tdp", _strong("Typical TDP")),
        ("other_names", _strong("Other names")),
        ("first_seen", _strong("CPU First Seen on Charts")),
        ("samples", r"Samples:\s*([\d,]+)"),
    ):
        v = _txt(pat, html)
        if v:
            out[key] = v
    m = re.search(r"Cores:</strong>\s*(\d+).*?Threads:</strong>\s*(\d+)", html, re.DOTALL)
    if m:
        out["cores"] = int(m.group(1))
        out["threads"] = int(m.group(2))
    for ck, cpat in (("l1i", r"L1 Instruction Cache:\s*([^<]{1,60})"),
                     ("l1d", r"L1 Data Cache:\s*([^<]{1,60})"),
                     ("l2", r"L2 Cache:\s*([^<]{1,60})"),
                     ("l3", r"L3 Cache:\s*([^<]{1,60})")):
        v = _txt(cpat, html)
        if v:
            out[f"cache_{ck}"] = v
    m = re.search(r"(\d+)(?:st|nd|rd|th) fastest in multithreading out of ([\d,]+)", html)
    if m:
        out["rank_mt"] = f"{m.group(1)} of {m.group(2)}"
    m = re.search(r"(\d+)(?:st|nd|rd|th) fastest in single threading out of ([\d,]+)", html)
    if m:
        out["rank_st"] = f"{m.group(1)} of {m.group(2)}"
    suite: dict[str, str] = {}
    for row in re.finditer(r"<tr>\s*<th[^>]*>([^<]{1,60})</th>\s*<td[^>]*>([^<]{1,60})</td>", html):
        suite[row.group(1).strip().lower()[:40]] = row.group(2).strip()[:60]
    if suite:
        out["suite"] = suite
    return out


def fetch_passmark_cpu(cpu: str, cache_days: int = 30) -> dict | None:
    """Returns {multi, single, source} or None. Cached; static fallback handled by caller."""
    key = cpu.strip().lower()
    with _lock:
        if key in _mem:
            return _mem[key]
        disk = _load()
        if key in disk and time.time() - disk[key].get("ts", 0) < cache_days * 86400:
            _mem[key] = disk[key]
            return disk[key]
    global _last_req
    with _lock:
        wait = 1.0 - (time.time() - _last_req)
    if wait > 0:
        time.sleep(wait)
    try:
        r = httpx.get(f"https://www.cpubenchmark.net/cpu.php?cpu={quote_plus(cpu)}",
                      headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"},
                      timeout=15, follow_redirects=True)
        with _lock:
            _last_req = time.time()
        if r.status_code != 200:
            return None
        multi, single = parse_passmark_detail(r.text)
        if multi is None:
            return None
        full = parse_passmark_full(r.text)
        out = {"multi": multi, "single": single, "source": "cpubenchmark.net", "ts": time.time(), **full}
        with _lock:
            _mem[key] = out
            disk = _load()
            disk[key] = out
            try:
                _cache_path.parent.mkdir(parents=True, exist_ok=True)
                _cache_path.write_text(json.dumps(disk))
            except Exception:
                pass
        return out
    except Exception:
        return None

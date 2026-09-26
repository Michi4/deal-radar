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


def closest_known_cpu(name: str) -> tuple[str | None, float]:
    """Closest real CPU when the exact page 404s: difflib over static DB + cached PassMark + GPU table."""
    import difflib
    want = _norm(name)
    candidates: dict[str, str] = {c: c for c in STATIC_DB}
    try:
        disk = _load()
        for k, v in disk.items():
            if isinstance(v, dict):
                candidates[k.replace("v2:", "")] = k.replace("v2:", "")
    except Exception:
        pass
    try:
        for k in _gpu_mem:
            candidates[k] = k
    except Exception:
        pass
    normed = {_norm(c): c for c in candidates}
    best = difflib.get_close_matches(want, list(normed), n=1, cutoff=0.75)
    if not best:
        return None, 0.0
    import difflib as _d
    score = _d.SequenceMatcher(None, want, best[0]).ratio()
    return normed[best[0]], round(score, 3)
    mt = re.search(r"Multithread Rating</div>\s*<div[^>]*>(\d+)</div>", html)
    st = re.search(r"Single Thread Rating</div>\s*<div[^>]*>(\d+)</div>", html)
    return (int(mt.group(1)) if mt else None, int(st.group(1)) if st else None)


GPU_LIST_URL = "https://www.videocardbenchmark.net/gpu_list.php"
_gpu_mem: dict[str, dict] = {}
_gpu_ts: float = 0.0


def parse_gpu_list(html: str) -> dict[str, dict]:
    """Row: <TR id=gpuN><TD><A ...>Name</A></TD><TD>G3D</TD><TD>rank?</TD>..."""
    out: dict[str, dict] = {}
    for m in re.finditer(
            r'<TR id="gpu\d+"><TD><A HREF="video_lookup\.php\?gpu=([^"&]+)&amp;id=(\d+)">([^<]{2,120})</A></TD><TD>(\d+)</TD>',
            html):
        _slug, gid, name, g3d = m.group(1), m.group(2), m.group(3), m.group(4)
        key = _norm(name.strip())
        try:
            out[key] = {"name": name.strip(), "g3d": int(g3d), "id": gid}
        except ValueError:
            continue
    return out


def fetch_gpu_table(cache_days: int = 7) -> dict[str, dict]:
    global _gpu_ts
    now = time.time()
    if _gpu_mem and now - _gpu_ts < cache_days * 86400:
        return _gpu_mem
    try:
        from curl_cffi import requests as _cr
        r = _cr.get(GPU_LIST_URL, impersonate="chrome124",
                    headers={"Accept-Language": "en-US,en;q=0.9"}, timeout=30)
        if r.status_code != 200:
            return _gpu_mem
        table = parse_gpu_list(r.text)
        if table:
            _gpu_mem.clear()
            _gpu_mem.update(table)
            _gpu_ts = now
    except Exception:
        pass
    return _gpu_mem


def lookup_gpu(name: str) -> dict | None:
    """Best-match GPU by normalized name (exact > startswith > contains)."""
    table = fetch_gpu_table()
    if not table:
        return None
    want = _norm(name)
    if want in table:
        return table[want]
    for k, v in table.items():
        if k.startswith(want) or want.startswith(k):
            return v
    for k, v in table.items():
        if want in k:
            return v
    return None


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


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def fetch_passmark_cpu(cpu: str, cache_days: int = 30) -> dict | None:
    """Returns {multi, single, ...} or None. Cached; static fallback handled by caller.
    VERIFIES the result page is actually about the requested CPU (fuzzy endpoint lies)."""
    key = "v2:" + cpu.strip().lower()  # v2: title-verified entries only
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
        # title check: "AMD Ryzen 5 PRO 5650U Benchmark" must contain the requested CPU
        title = re.search(r"<title>([^<]{3,120})", r.text)
        if not title or _norm(cpu) not in _norm(title.group(1)):
            return None  # fuzzy endpoint returned a different CPU — refuse wrong scores
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

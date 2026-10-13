#!/usr/bin/env python3
"""One-command deal hunt for humans and AI agents.

Fires N keyword searches, waits for completion, then prints the ranked
value board (perf/euro, boards, platforms) with links as markdown (or JSON).

Usage:
    PYTHONPATH=packages .venv/bin/python scripts/hunt.py \\
        --base http://localhost:8090 -q "ryzen mini pc" -q "laptop mainboard" \\
        --sources kleinanzeigen,vinted,willhaben,shpock --limit 35

Env: HUNT_BASE overrides --base. No secrets needed (same-origin dev use).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request


def _req(base: str, method: str, path: str, payload: dict | None = None,
         timeout: int = 60) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def _start(base: str, q: str, sources: list[str], limit: int) -> str:
    r = _req(base, "POST", "/searches",
             {"keywords": q, "sources": sources, "limit": limit,
              "enrich": True, "benchmarks": True}, timeout=120)
    return r["id"]


def _wait(base: str, sid: str, deadline: float) -> dict:
    while time.time() < deadline:
        d = _req(base, "GET", f"/searches/{sid}", timeout=120)
        if d.get("status") in ("done", "stopped", "failed", "interrupted"):
            return d
        time.sleep(10)
    return {"id": sid, "status": "timeout"}


def _row(x: dict) -> str:
    price = f"{x.get('price') if x.get('price') is not None else '?'} {x.get('currency') or ''}".strip()
    extra = ""
    if x.get("board") and x.get("eff_price"):
        extra += f" (≈{x['eff_price']} built)"
    elif x.get("full_price") and x["full_price"] != x.get("price"):
        extra += f" (≈{x['full_price']} complete)"
    if x.get("board"):
        mark = x.get("eff_ppe") or 0
    else:
        mark = x.get("ppe_full") or x.get("ppe") or 0
    cpu = x.get("cpu") or "?"
    mt = x.get("multi") or "?"
    est = " (est.)" if x.get("estimated") else ""
    return (f"| {x.get('title','?')[:70]} | {price}{extra} | {cpu}{est} {mt} | "
            f"{mark} | {x.get('source','')} | {x.get('url','')} |")


def main() -> int:
    ap = argparse.ArgumentParser(description="ranked multi-query deal hunt")
    ap.add_argument("--base", default="http://localhost:8090")
    ap.add_argument("-q", "--query", action="append", default=[],
                    help="keyword query (repeatable)")
    ap.add_argument("--sources", default="kleinanzeigen,vinted,willhaben,shpock")
    ap.add_argument("--limit", type=int, default=35)
    ap.add_argument("--days", type=float, default=1.0)
    ap.add_argument("--board-limit", type=int, default=30)
    ap.add_argument("--min-bench", type=int, default=8000)
    ap.add_argument("--timeout-min", type=float, default=15.0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    import os
    base = os.getenv("HUNT_BASE", a.base).rstrip("/")
    if not a.query:
        print("no queries: pass at least one -q", file=sys.stderr)
        return 2
    sources = [s.strip() for s in a.sources.split(",") if s.strip()]
    deadline = time.time() + a.timeout_min * 60
    sids = []
    for q in a.query:
        try:
            sid = _start(base, q, sources, a.limit)
            print(f"started {sid} <- {q}", file=sys.stderr)
            sids.append((sid, q))
        except Exception as e:
            print(f"FAILED to start {q!r}: {e}", file=sys.stderr)
    for sid, q in sids:
        try:
            d = _wait(base, sid, deadline)
            n = len(d.get("results", []))
            print(f"{sid} {d.get('status')} ({n} results) <- {q}", file=sys.stderr)
        except Exception as e:
            print(f"{sid} poll failed: {e}", file=sys.stderr)
    try:
        board = _req(base, "GET", f"/gems/board?days={a.days}&limit={a.board_limit}"
                                  f"&min_bench={a.min_bench}", timeout=120)
    except Exception as e:
        print(f"gems board failed: {e}", file=sys.stderr)
        return 1
    if a.json:
        print(json.dumps(board, ensure_ascii=False, indent=1))
        return 0
    head = "| deal | price | cpu MT | pts/€ | source | link |"
    sep = "|---|---|---|---|---|---|"
    print(f"## Top perf/€ (complete cost, n={board.get('n')}, "
          f"rated={board.get('rated')}, est={board.get('estimated')}, "
          f"systems w/o data={board.get('unrated_systems')}, "
          f"non-systems={board.get('unrated_nonsystem')})")
    print(head + "\n" + sep)
    for x in (board.get("ppe") or [])[:20]:
        print(_row(x))
    print("\n## Boards (effective build cost)")
    print(head + "\n" + sep)
    for x in (board.get("boards") or [])[:20]:
        print(_row(x))
    print("\n## Platforms (need CPU/board build)")
    for x in (board.get("platforms") or [])[:15]:
        print(f"| {x.get('title','?')[:70]} | {x.get('price')} {x.get('currency') or ''} "
              f"| {x.get('cpu') or '?'} | {x.get('source','')} | {x.get('url','')} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

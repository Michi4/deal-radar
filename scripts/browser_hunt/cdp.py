#!/usr/bin/env python3
"""Minimal CDP driver: navigate + evaluate in the debug Chrome, with retries.

Usage:
    python3 cdp.py <url> <js-expression-file-or-inline> [wait_ms]
"""
import json
import subprocess
import sys
import time
import urllib.request
from urllib.parse import quote

CDP = "http://localhost:9222"


def _get(path):
    with urllib.request.urlopen(CDP + path, timeout=15) as r:
        return json.loads(r.read())


def _ws_url():
    targets = _get("/json/list")
    pages = [t for t in targets if t["type"] == "page"]
    # prefer a normal http page over chrome:// ones
    for p in pages:
        if p["url"].startswith("http"):
            return p["webSocketDebuggerUrl"]
    if pages:
        return pages[0]["webSocketDebuggerUrl"]
    new = _get("/json/new?" + quote("about:blank", safe=""))
    return new["webSocketDebuggerUrl"]


class CDPError(RuntimeError):
    pass


def run(js, url=None, wait_ms=3500, timeout=60, navigate_first=True):
    """Open a fresh tab (or reuse), optionally navigate, then evaluate js."""
    ws = _ws_url()
    try:
        import websocket  # type: ignore
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                        "websocket-client"], check=True)
        import websocket  # type: ignore

    sock = websocket.create_connection(ws, timeout=timeout,
                                       origin="http://localhost:9222")
    mid = 0

    def send(method, params=None):
        nonlocal mid
        mid += 1
        sock.send(json.dumps({"id": mid, "method": method,
                              "params": params or {}}))
        while True:
            raw = sock.recv()
            if not isinstance(raw, str):
                continue
            msg = json.loads(raw)
            if msg.get("id") == mid:
                if "error" in msg:
                    raise CDPError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    try:
        if url and navigate_first:
            send("Page.enable")
            send("Page.navigate", {"url": url})
            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    st = send("Runtime.evaluate", {
                        "expression": "document.readyState",
                        "returnByValue": True})
                    if st.get("result", {}).get("value") == "complete":
                        break
                except CDPError:
                    pass
                time.sleep(0.35)
        if wait_ms:
            time.sleep(wait_ms / 1000.0)
        send("Runtime.enable")
        res = send("Runtime.evaluate", {
            "expression": js, "returnByValue": True,
            "awaitPromise": True, "timeout": timeout * 1000})
        if "exceptionDetails" in res:
            raise CDPError(str(res["exceptionDetails"])[:400])
        return res.get("result", {}).get("value")
    finally:
        try:
            sock.close()
        except Exception:
            pass


def navigate(url, wait_ms=3000, timeout=60):
    """Just load a page (keeps the tab focused for manual/debug use)."""
    return run("location.href", url=url, wait_ms=wait_ms, timeout=timeout)


if __name__ == "__main__":
    u = sys.argv[1]
    expr = sys.argv[2]
    if expr.startswith("/") or expr.endswith(".js") or expr.endswith(".txt"):
        expr = open(expr).read()
    wait = int(sys.argv[3]) if len(sys.argv) > 3 else 3500
    out = run(expr, url=u, wait_ms=wait)
    print(json.dumps(out, ensure_ascii=False, indent=1) if isinstance(
        out, (dict, list)) else out)

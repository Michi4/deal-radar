import urllib.request, json, time, threading

BASE = "http://localhost:8099"
got = {}


def listen(tag, seconds=90):
    import socket
    s = socket.create_connection(("localhost", 8099), timeout=seconds + 10)
    s.sendall(b"GET /stream HTTP/1.0\r\nAccept: text/event-stream\r\n\r\n")
    s.settimeout(seconds)
    buf = b""
    t0 = time.time()
    try:
        while time.time() - t0 < seconds:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
            if b"search_done" in buf:
                got[tag] = round(time.time() - t0, 1)
                break
    except Exception as e:
        got[tag] = f"err {e}"
    finally:
        s.close()


t = threading.Thread(target=listen, args=("first", 120), daemon=True)
t.start()
time.sleep(3)
r = urllib.request.Request(BASE + "/searches",
                           data=json.dumps({"keywords": "ThinkPad T410", "sources": ["kleinanzeigen"],
                                            "limit": 3, "ocr": False, "vision": False,
                                            "details": False, "benchmarks": False}).encode(),
                           headers={"Content-Type": "application/json"})
sid = json.load(urllib.request.urlopen(r, timeout=60))["id"]
print("job:", sid)
t0 = time.time()
for _ in range(40):
    time.sleep(10)
    d = json.load(urllib.request.urlopen(f"{BASE}/searches/{sid}", timeout=60))
    if d.get("status") == "done":
        break
t.join(timeout=30)
print("SSE saw search_done after connect:", got.get("first"), "job total:", round(time.time() - t0), "s")
# reconnect test: fresh connection must stream (keep-alive) without error
t2 = threading.Thread(target=listen, args=("reconnect", 25), daemon=True)
t2.start()
t2.join(timeout=40)
print("reconnect stream alive (no search_done expected):", "reconnect" not in got)
urllib.request.urlopen(urllib.request.Request(f"{BASE}/searches/{sid}", method="DELETE"), timeout=15)
print("cleaned")

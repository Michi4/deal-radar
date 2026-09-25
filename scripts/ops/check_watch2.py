import urllib.request, json, time


def api(path, data=None, timeout=120):
    r = urllib.request.Request("http://localhost:8099" + path,
                               data=json.dumps(data).encode() if data else None,
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=timeout))


def runs():
    return api("/metrics.json", timeout=30)["metrics"]["counters"].get("search_runs", 0)


if __name__ == "__main__":
    s = api("/searches", {"keywords": "ThinkPad X1", "sources": ["kleinanzeigen"],
                          "limit": 4, "watch": True, "poll_interval_s": 45,
                          "ocr": False, "vision": False, "details": False})
    print("watch job:", s["id"], s["status"])
    time.sleep(75)
    print("search_runs now:", runs())
    print("WATCH_POLLS: check metrics delta in output above (must grow)")
    urllib.request.urlopen(urllib.request.Request(
        f"http://localhost:8099/searches/{s['id']}", method="DELETE"), timeout=15)
    print("watch deleted")

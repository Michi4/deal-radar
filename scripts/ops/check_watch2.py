import urllib.request, json, time


def api(path, data=None, timeout=120):
    r = urllib.request.Request("http://localhost:8099" + path,
                               data=json.dumps(data).encode() if data else None,
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=timeout))


def runs():
    return api("/metrics.json", timeout=30)["metrics"]["counters"].get("search_runs", 0)


if __name__ == "__main__":
    s = api("/searches", {"keywords": "ThinkPad X1 Carbon", "sources": ["kleinanzeigen"],
                          "limit": 4, "watch": True, "poll_interval_s": 45,
                          "ocr": False, "vision": False, "details": False})
    sid = s["id"]
    print("watch job:", sid)
    time.sleep(20)
    m1 = runs()
    print("baseline search_runs:", m1)
    # wait long enough for initial job + one watcher repoll (interval 45s)
    for _ in range(10):
        time.sleep(30)
        m2 = runs()
        print("search_runs:", m2)
        if m2 > m1:
            print("WATCH_REPOLL_OK")
            break
    else:
        print("WATCH_REPOLL_FAIL")
    urllib.request.urlopen(urllib.request.Request(
        f"http://localhost:8099/searches/{sid}", method="DELETE"), timeout=15)
    print("watch deleted")

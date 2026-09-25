import urllib.request, json, time


def api(path, data=None, timeout=120):
    r = urllib.request.Request("http://localhost:8099" + path,
                               data=json.dumps(data).encode() if data else None,
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=timeout))


if __name__ == "__main__":
    s = api("/searches", {"keywords": "ThinkPad X1 Yoga", "sources": ["kleinanzeigen"],
                          "limit": 4, "watch": True, "poll_interval_s": 60,
                          "ocr": False, "vision": False, "details": False})
    print("watch created:", s["id"], "WAITING for initial job to finish + persist...")
    for _ in range(20):
        time.sleep(15)
        try:
            d = api(f"/searches/{s['id']}", timeout=30)
        except Exception as e:
            print("poll err", str(e)[:60])
            continue
        if d.get("status") == "done":
            print("initial done, results:", len(d.get("results", [])))
            break
    print("SID_FOR_RESTART_TEST:", s["id"])

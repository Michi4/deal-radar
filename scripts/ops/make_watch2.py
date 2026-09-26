import urllib.request, json, time


def post(path, data, timeout=120):
    r = urllib.request.Request("http://localhost:8099" + path, data=json.dumps(data).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=timeout))


def get(path, timeout=60):
    return json.load(urllib.request.urlopen("http://localhost:8099" + path, timeout=timeout))


j = post("/searches", {"keywords": "ThinkPad T410", "sources": ["kleinanzeigen"],
                       "limit": 3, "watch": True, "poll_interval_s": 60,
                       "ocr": False, "vision": False, "details": False, "benchmarks": False})
print("watch job:", j["id"])
for _ in range(30):
    time.sleep(10)
    d = get(f"/searches/{j['id']}")
    if d.get("status") == "done":
        print("done, results:", len(d.get("results", [])))
        break
print("SID:", j["id"])

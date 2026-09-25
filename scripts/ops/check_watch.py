import urllib.request, json, time

BASE = "http://localhost:8099"


def post(path, data):
    r = urllib.request.Request(BASE + path, data=json.dumps(data).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=120))


def get(path):
    return json.load(urllib.request.urlopen(BASE + path, timeout=30))


def runs():
    return get("/metrics.json")["metrics"]["counters"].get("search_runs", 0)


s = post("/searches", {"keywords": "ThinkPad T14", "sources": ["kleinanzeigen"],
                       "limit": 5, "watch": True, "poll_interval_s": 45})
sid = s["id"]
print("watch:", sid, "results:", len(s["results"]))
m1 = runs()
print("searches run:", m1)
time.sleep(60)
m2 = runs()
print("searches run after 60s:", m2)
print("WATCHER_REPOLL:", "OK" if m2 > m1 else "FAIL")
req = urllib.request.Request(BASE + "/searches/" + sid, method="DELETE")
urllib.request.urlopen(req, timeout=15)
print("deleted")

import urllib.request, json


def post(path, data):
    r = urllib.request.Request("http://localhost:8099" + path, data=json.dumps(data).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=120))


def get(path):
    return json.load(urllib.request.urlopen("http://localhost:8099" + path, timeout=30))


print("before:", get("/metrics.json")["metrics"]["counters"].get("search_runs"))
s = post("/searches", {"keywords": "ThinkPad", "sources": ["kleinanzeigen"], "limit": 3})
print("results:", len(s["results"]))
print("after:", get("/metrics.json")["metrics"]["counters"].get("search_runs"))
print("all counters:", get("/metrics.json")["metrics"]["counters"])

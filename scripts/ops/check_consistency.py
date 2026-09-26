import urllib.request, json


def get(path, timeout=60):
    return json.load(urllib.request.urlopen("http://localhost:8099" + path, timeout=timeout))


m = get("/metrics.json")
print("watchlist:", len(m.get("watchlist", [])), "events:", m.get("events"))
c = m["metrics"]["counters"]
print("search_runs:", c.get("search_runs"), "scored:", c.get("listings_scored"))
import urllib.request as _u
t = _u.urlopen("http://localhost:8099/metrics", timeout=30).read().decode()
n = sum(1 for line in t.split("\n") if line.startswith("dealradar_"))
print("prometheus lines:", n, "| consistent:", n > 5 and c.get("search_runs", 0) >= 0)

import urllib.request, json

m = json.load(urllib.request.urlopen("http://localhost:8099/metrics.json", timeout=30))
mine = [s["id"] for s in m.get("watchlist", [])
        if s.get("keywords", "").startswith("ThinkPad X1")]
print("mine to delete:", len(mine))
for sid in mine:
    urllib.request.urlopen(urllib.request.Request(
        f"http://localhost:8099/searches/{sid}", method="DELETE"), timeout=15)
print("deleted test watches, user searches untouched")

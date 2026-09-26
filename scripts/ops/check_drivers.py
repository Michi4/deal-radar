import urllib.request, json

d = json.load(urllib.request.urlopen("http://localhost:8099/drivers", timeout=30))
print("drivers:", sorted(x["id"] for x in d))
d2 = json.load(urllib.request.urlopen("http://localhost:8099/marketplace", timeout=30))
print("marketplace drivers:", sorted(x["id"] for x in d2["drivers"]))

import urllib.request, json

d = json.load(urllib.request.urlopen("http://localhost:8099/marketplace", timeout=30))
print("drivers:", [(x["id"], x["installed"]) for x in d["drivers"]])
print("enrichers:", [(x["id"], x["installed"]) for x in d["enrichers"]])
h = json.load(urllib.request.urlopen("http://localhost:8099/health", timeout=15))
print("drivers live:", h["drivers"])

import urllib.request, json

r = urllib.request.Request(
    "http://localhost:8099/lab/build",
    data=json.dumps({"kind": "enricher",
                     "instruction": "flag listings whose title contains the word 'B-Ware' or 'refurbished' with a refurbished=true fact at 0.9 confidence"}).encode(),
    headers={"Content-Type": "application/json"})
d = json.load(urllib.request.urlopen(r, timeout=300))
print("ok:", d.get("ok"), "| id:", d.get("id"), "| checks:", json.dumps(d.get("checks", {}))[:200])
print("err:", d.get("error"))
s = json.load(urllib.request.urlopen("http://localhost:8099/lab/status", timeout=30))
print("enrichers:", s["enrichers"])

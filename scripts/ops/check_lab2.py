import urllib.request, json

r = urllib.request.Request(
    "http://localhost:8099/lab/build",
    data=json.dumps({"kind": "enricher",
                     "instruction": "flag listings whose title or description mentions warranty, garantie, gewährleistung or 12 monate garantie with a warranty=true fact at 0.85 confidence, otherwise no facts"}).encode(),
    headers={"Content-Type": "application/json"})
d = json.load(urllib.request.urlopen(r, timeout=300))
print("ok:", d.get("ok"), "| id:", d.get("id"))
print("checks:", json.dumps(d.get("checks", {}))[:250])
print("err:", d.get("error"))
s = json.load(urllib.request.urlopen("http://localhost:8099/lab/status", timeout=30))
print("enrichers:", s["enrichers"])

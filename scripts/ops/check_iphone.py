import urllib.request, json

q = {"text": "iphone which uses a usb c plug to charge", "limit": 14}
r = urllib.request.Request(
    "http://localhost:8099/searches/nl",
    data=json.dumps(q).encode(), headers={"Content-Type": "application/json"})
d = json.load(urllib.request.urlopen(r, timeout=300))
print("models:", d["parsed"].get("models", [])[:8])
print("results:", len(d["results"]), "filtered:", d.get("filtered_out"))
for x in d["results"][:10]:
    print("-", x["listing"]["title"][:55], "|", x["listing"]["price"],
          "|", x["listing"]["source"])
m = json.load(urllib.request.urlopen("http://localhost:8099/metrics.json", timeout=15))
c = m["metrics"]["counters"]
print("stage_b:", c.get("stage_b_total"), "vision:", c.get("vision_total"))

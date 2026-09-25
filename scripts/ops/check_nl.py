import urllib.request, json

q = {"text": "iphone which uses a usb c plug to charge", "limit": 12}
r = urllib.request.Request("http://localhost:8099/searches/nl",
                           data=json.dumps(q).encode(), headers={"Content-Type": "application/json"})
d = json.load(urllib.request.urlopen(r, timeout=300))
print("keywords:", d["parsed"].get("keywords"))
print("models:", d["parsed"].get("models", [])[:6])
print("blacklist:", [b.get("value") for b in d["parsed"].get("blacklist", [])][:8])
print("results:", len(d["results"]), "filtered:", d.get("filtered_out"), "errors:", d.get("driver_errors"))
print("subqueries:", d.get("subqueries"))

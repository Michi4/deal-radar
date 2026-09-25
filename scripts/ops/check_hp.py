import urllib.request, json

q = {"text": "hp elitebook 845 g8", "limit": 10, "vision": False}
r = urllib.request.Request("http://localhost:8099/searches/nl",
                           data=json.dumps(q).encode(), headers={"Content-Type": "application/json"})
d = json.load(urllib.request.urlopen(r, timeout=300))
print("models:", d["parsed"].get("models", [])[:5])
print("results:", len(d["results"]), "filtered:", d.get("filtered_out"), "errors:", d.get("driver_errors"))
for x in d["results"][:8]:
    en = {e["field"]: e["value"] for e in x.get("enrichments", [])}
    print("-", x["listing"]["title"][:50], "|", x["listing"]["price"],
          "| cpu:", en.get("cpu"), "| bench:", en.get("cpu_benchmark"),
          "| cores:", en.get("cpu_cores"), "| rank:", en.get("cpu_rank_mt"),
          "| why:", [w for w in x["why"] if "CPU" in w or "CONTRADICTION" in w][:2])

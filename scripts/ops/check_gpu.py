import urllib.request, json

q = {"keywords": "Legion RTX 3060", "sources": ["kleinanzeigen"], "limit": 8,
     "ocr": False, "vision": False, "details": False}
r = urllib.request.Request("http://localhost:8099/searches",
                           data=json.dumps(q).encode(), headers={"Content-Type": "application/json"})
d = json.load(urllib.request.urlopen(r, timeout=300))
print("results:", len(d["results"]), "errors:", d.get("driver_errors"))
for x in d["results"][:8]:
    en = {e["field"]: e["value"] for e in x.get("enrichments", [])}
    print("-", x["listing"]["title"][:50], "|", x["listing"]["price"],
          "| gpu:", en.get("gpu"), "| g3d:", en.get("gpu_benchmark"),
          "| cpu:", en.get("cpu"), "| bench:", en.get("cpu_benchmark"))

import urllib.request, json, time


def post(path, data, timeout=120):
    r = urllib.request.Request("http://localhost:8099" + path, data=json.dumps(data).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=timeout))


def get(path, timeout=60):
    return json.load(urllib.request.urlopen("http://localhost:8099" + path, timeout=timeout))


j = post("/searches", {"keywords": "ThinkPad T480", "sources": ["kleinanzeigen"],
                       "limit": 8, "ocr": False, "vision": False, "details": False})
sid = j["id"]
for _ in range(40):
    time.sleep(10)
    d = get(f"/searches/{sid}")
    if d.get("status") == "done":
        break
found = [(x["listing"]["title"][:45], [e for e in x["enrichments"] if e["field"] == "warranty"])
         for x in d.get("results", [])]
print("results:", len(d.get("results", [])))
for t, w in found:
    print("-", t, "| warranty:", w[0]["value"] if w else None)

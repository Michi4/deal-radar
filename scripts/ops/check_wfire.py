import urllib.request, json, time


def post(path, data, timeout=120):
    r = urllib.request.Request("http://localhost:8099" + path, data=json.dumps(data).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=timeout))


def get(path, timeout=60):
    return json.load(urllib.request.urlopen("http://localhost:8099" + path, timeout=timeout))


j = post("/searches", {"keywords": "ThinkPad Garantie", "sources": ["kleinanzeigen"],
                       "limit": 8, "ocr": False, "vision": False, "details": False})
sid = j["id"]
for _ in range(40):
    time.sleep(10)
    d = get(f"/searches/{sid}")
    if d.get("status") == "done":
        break
hits = 0
for x in d.get("results", [])[:8]:
    w = [e for e in x.get("enrichments", []) if e["field"] == "warranty"]
    if w:
        hits += 1
        print("FIRED:", x["listing"]["title"][:55], "->", w[0]["value"], w[0].get("confidence"))
print("results:", len(d.get("results", [])), "warranty hits:", hits)

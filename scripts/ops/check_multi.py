import urllib.request, json, time


def post(path, data, timeout=120):
    r = urllib.request.Request("http://localhost:8099" + path, data=json.dumps(data).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=timeout))


def get(path, timeout=60):
    return json.load(urllib.request.urlopen("http://localhost:8099" + path, timeout=timeout))


j = post("/searches", {"keywords": "rtx 4070 laptop; rtx 4060 laptop", "sources": ["kleinanzeigen"],
                       "limit": 12, "ocr": False, "vision": False, "details": False, "benchmarks": False})
d = j
for _ in range(60):
    time.sleep(10)
    d = get(f"/searches/{j['id']}")
    if d.get("status") == "done":
        break
print("subqueries:", d.get("subqueries"))
print("results:", len(d.get("results", [])), "errors:", d.get("driver_errors"))
import re
hits4070 = hits4060 = 0
for x in d.get("results", [])[:12]:
    t = (x["listing"]["title"] or "").lower()
    if "4070" in t:
        hits4070 += 1
    if "4060" in t:
        hits4060 += 1
    print("-", x["listing"]["title"][:55], "|", x["listing"]["price"])
print("4070 hits:", hits4070, "4060 hits:", hits4060)

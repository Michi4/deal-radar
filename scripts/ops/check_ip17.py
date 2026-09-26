import urllib.request, json, time


def post(path, data, timeout=120):
    r = urllib.request.Request("http://localhost:8099" + path, data=json.dumps(data).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=timeout))


def get(path, timeout=60):
    return json.load(urllib.request.urlopen("http://localhost:8099" + path, timeout=timeout))


j = post("/searches/nl", {"text": "iphone 17", "limit": 10, "vision": False,
                          "details": False, "benchmarks": False, "sources": ["willhaben"]})
d = j
for _ in range(60):
    time.sleep(10)
    d = get(f"/searches/{j['id']}")
    if d.get("status") == "done":
        break
p = d.get("parsed", {})
print("keywords:", p.get("keywords"))
print("models:", p.get("models", [])[:8])
print("hard:", json.dumps(p.get("hard", {}))[:300])
print("blacklist:", [b.get("value") for b in p.get("blacklist", [])][:12])
print("subqueries:", d.get("subqueries"))
print("results:", len(d.get("results", [])), "filtered:", d.get("filtered_out"), "errors:", d.get("driver_errors"))
m = get("/metrics.json")["metrics"]["counters"]
print({k: v for k, v in m.items() if "willhaben" in k or "filter" in k or "model" in k})
for x in d.get("results", [])[:6]:
    print("-", x["listing"]["title"][:55], "|", x["listing"]["price"])

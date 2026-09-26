import urllib.request, json, time


def post(path, data, timeout=120):
    r = urllib.request.Request("http://localhost:8099" + path, data=json.dumps(data).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=timeout))


def get(path, timeout=60):
    return json.load(urllib.request.urlopen("http://localhost:8099" + path, timeout=timeout))


for q in ["hp elitebook 845 g8", "gaming laptop rtx 4070 16gb ram"]:
    j = post("/searches/nl", {"text": q, "limit": 2, "vision": False,
                              "details": False, "benchmarks": False,
                              "sources": ["kleinanzeigen"]})
    d = j
    for _ in range(60):
        time.sleep(10)
        d = get(f"/searches/{j['id']}")
        if d.get("status") == "done":
            break
    p = d.get("parsed", {})
    print(f"Q: {q}")
    print(f"  models={p.get('models', [])[:5]}")
    print(f"  attrs={p.get('attributes', {})} results={len(d.get('results', []))}")

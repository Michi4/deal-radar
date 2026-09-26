import urllib.request, json, time


def post(path, data, timeout=120):
    r = urllib.request.Request("http://localhost:8099" + path, data=json.dumps(data).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=timeout))


def get(path, timeout=60):
    return json.load(urllib.request.urlopen("http://localhost:8099" + path, timeout=timeout))


j = post("/searches/nl", {"text": "iphone with usb c charging", "limit": 2, "vision": False,
                          "details": False, "benchmarks": False, "sources": ["kleinanzeigen"]})
print("job:", j)
for _ in range(60):
    time.sleep(10)
    d = get(f"/searches/{j['id']}")
    if d.get("status") == "done":
        break
print("status:", d.get("status"))
print("parsed:", json.dumps(d.get("parsed"), ensure_ascii=False)[:600])
print("results:", len(d.get("results", [])), "errors:", d.get("driver_errors"))

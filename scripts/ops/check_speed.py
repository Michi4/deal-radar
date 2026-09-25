import urllib.request, json, time


def post(path, data, timeout=180):
    r = urllib.request.Request("http://localhost:8099" + path, data=json.dumps(data).encode(),
                               headers={"Content-Type": "application/json"})
    t = time.time()
    d = json.load(urllib.request.urlopen(r, timeout=timeout))
    return d, round(time.time() - t, 1)


d, t = post("/searches", {"keywords": "ThinkPad", "sources": ["kleinanzeigen", "willhaben"],
                          "limit": 10, "ocr": False, "benchmarks": False, "vision": False, "details": False})
print(f"keyword search: {len(d['results'])} results in {t}s")
d, t = post("/searches", {"keywords": "ThinkPad", "sources": ["kleinanzeigen", "willhaben"],
                          "limit": 10, "ocr": False, "benchmarks": False, "vision": False, "details": False})
print(f"cached repeat: {len(d['results'])} results in {t}s")

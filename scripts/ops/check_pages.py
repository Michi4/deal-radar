import urllib.request, json, time


def post(path, data, timeout=120):
    r = urllib.request.Request("http://localhost:8099" + path, data=json.dumps(data).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=timeout))


def get(path, timeout=60):
    return json.load(urllib.request.urlopen("http://localhost:8099" + path, timeout=timeout))


def counters():
    return get("/metrics.json")["metrics"]["counters"]


if __name__ == "__main__":
    before = counters()
    j = post("/searches", {"keywords": "ThinkPad", "limit": 60,
                           "ocr": False, "vision": False, "details": False, "benchmarks": False})
    sid = j["id"]
    for _ in range(60):
        time.sleep(10)
        d = get(f"/searches/{sid}")
        if d.get("status") == "done":
            break
    after = counters()
    for k in sorted(after):
        if k.startswith("driver_") and k.endswith("_fetched"):
            print(k, after[k] - before.get(k, 0))
    print("results:", len(d.get("results", [])), "filtered:", d.get("filtered_out"),
          "errors:", d.get("driver_errors"))

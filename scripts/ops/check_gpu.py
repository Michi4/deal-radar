import urllib.request, json, time


def api(path, data=None, timeout=120):
    r = urllib.request.Request("http://localhost:8099" + path,
                               data=json.dumps(data).encode() if data else None,
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=timeout))


def run_search(payload, timeout=400):
    j = api("/searches", payload)
    sid = j["id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        d = api(f"/searches/{sid}", timeout=60)
        if d.get("status") == "running":
            time.sleep(4)
            continue
        return d
    raise TimeoutError("job did not finish")


if __name__ == "__main__":
    d = run_search({"keywords": "Legion RTX 3060", "sources": ["kleinanzeigen"], "limit": 8,
                    "ocr": False, "vision": False, "details": False})
    print("results:", len(d["results"]), "errors:", d.get("driver_errors"))
    for x in d["results"][:8]:
        en = {e["field"]: e["value"] for e in x.get("enrichments", [])}
        print("-", x["listing"]["title"][:50], "|", x["listing"]["price"],
              "| gpu:", en.get("gpu"), "| g3d:", en.get("gpu_benchmark"),
              "| cpu:", en.get("cpu"), "| bench:", en.get("cpu_benchmark"))

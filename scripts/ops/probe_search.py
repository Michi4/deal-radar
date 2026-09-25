import urllib.request, json, time, sys

BASE = "http://localhost:8099"


def post(path, data, timeout=120):
    r = urllib.request.Request(BASE + path, data=json.dumps(data).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=timeout))


def get(path, timeout=60):
    return json.load(urllib.request.urlopen(BASE + path, timeout=timeout))


def run(name, payload, timeout=500):
    j = post("/searches", payload)
    sid = j["id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        d = get(f"/searches/{sid}")
        if d.get("status") == "running":
            time.sleep(5)
            continue
        n = len(d.get("results", []))
        print(f"{name}: status={d.get('status')} results={n} filtered={d.get('filtered_out')} "
              f"errors={d.get('driver_errors')} elapsed={round(time.time()-t0)}s")
        for x in d.get("results", [])[:5]:
            print("  -", (x["listing"]["title"] or "")[:55], "|", x["listing"]["price"],
                  "|", x["listing"]["source"], "| match:", x.get("match_score"))
        return d
    print(name, "TIMEOUT")
    return {}


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "thinkpad"
    if which == "thinkpad":
        run("thinkpad", {"keywords": "ThinkPad", "limit": 20})
    elif which == "iphone17":
        run("iphone17", {"keywords": "iPhone 17", "limit": 30})

import urllib.request, json, time


def api(path, data=None, method=None, timeout=120):
    r = urllib.request.Request("http://localhost:8099" + path,
                               data=json.dumps(data).encode() if data else None,
                               headers={"Content-Type": "application/json"},
                               method=method)
    return json.load(urllib.request.urlopen(r, timeout=timeout))


def run_search(payload, timeout=400):
    j = api("/searches", payload)
    sid = j["id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        d = api(f"/searches/{sid}", timeout=60)
        if d.get("status") == "running":
            time.sleep(5)
            continue
        return d
    raise TimeoutError("job did not finish")


if __name__ == "__main__":
    d = run_search({"keywords": "ThinkPad T460", "sources": ["kleinanzeigen"], "limit": 5,
                    "ocr": False, "vision": False, "details": False})
    lid = d["results"][0]["listing"]["id"]
    print("fav target:", d["results"][0]["listing"]["title"][:50])
    print("fav:", api(f"/favorites/{lid}", {}, method="POST"))
    f = api("/favorites")
    mine = [x for x in f if x["listing_id"] == lid]
    print("favorites has it:", len(mine) == 1, "| title:", (mine[0]["title"] or "")[:40])
    print("unfav:", api(f"/favorites/{lid}", method="DELETE"))
    f2 = api("/favorites")
    print("gone after delete:", all(x["listing_id"] != lid for x in f2))

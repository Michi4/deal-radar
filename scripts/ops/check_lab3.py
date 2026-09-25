import urllib.request, json, sys

BASE = "http://localhost:8099"


def post(path, data, timeout=300):
    r = urllib.request.Request(BASE + path, data=json.dumps(data).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=timeout))


if __name__ == "__main__":
    # rebuild warranty detector with the fixed contract prompt
    d = post("/lab/build", {"kind": "enricher",
                            "instruction": "flag listings whose title or description mentions warranty, garantie or gewaehrleistung with a warranty=true fact at 0.85 confidence, otherwise no facts"})
    print("build ok:", d.get("ok"), "| checks:", json.dumps(d.get("checks", {}))[:300])
    print("err:", d.get("error"))

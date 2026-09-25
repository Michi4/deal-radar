import urllib.request, json

q = {"text": "iphone which uses a usb c plug to charge", "limit": 12}
r = urllib.request.Request("http://localhost:8099/searches/nl",
                           data=json.dumps(q).encode(), headers={"Content-Type": "application/json"})
sid = json.load(urllib.request.urlopen(r, timeout=300))["id"]
print("sid:", sid)
c = json.load(urllib.request.urlopen(f"http://localhost:8099/searches/{sid}/compare", timeout=60))
print("groups:", len(c["groups"]))
for m, rows in list(c["groups"].items())[:6]:
    pr = [x["price"] for x in rows if x["price"]]
    print(f"- {m}: n={len(rows)} min={min(pr) if pr else '?'} srcs={sorted(set(x['source'] for x in rows))}")

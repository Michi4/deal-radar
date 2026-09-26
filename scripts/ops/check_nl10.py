import urllib.request, json, time


def post(path, data, timeout=120):
    r = urllib.request.Request("http://localhost:8099" + path, data=json.dumps(data).encode(),
                               headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=timeout))


def get(path, timeout=60):
    return json.load(urllib.request.urlopen("http://localhost:8099" + path, timeout=timeout))


QUERIES = [
    "iphone with usb c charging",
    "ThinkPad unter 700 ohne defekt",
    "oled laptop under 1000",
    "hp elitebook 845 g8",
    "rtx 3060 laptop",
    "iphone 15 pro max 256gb",
    "Samsung Galaxy S24 mit 5G",
    "leise Tastatur Laptop fuer Buero",
    "camera for low light photography under 800",
    "gaming laptop rtx 4070 16gb ram",
]

for q in QUERIES:
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
    print(f"Q: {q[:45]}")
    print(f"  -> keywords={p.get('keywords')!r} models={p.get('models', [])[:4]} "
          f"attrs={p.get('attributes', {})} results={len(d.get('results', []))}")

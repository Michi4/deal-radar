import urllib.request, json

QUERIES = [
    "iphone with usb c charging",
    "ThinkPad unter 700 ohne defekt",
    "oled laptop under 1000",
    "hp elitebook 845 g8",
    "rtx 3060 laptop",
    "iphone 15 pro max 256gb",
    "Samsung Galaxy S24 mit 5G",
    "leise Tastatur Laptop für Büro",
    "camera for low light photography under 800",
    "gaming laptop rtx 4070 16gb ram",
]

r = urllib.request.Request("http://localhost:8099/lab/build", data=b"{}",
                           headers={"Content-Type": "application/json"})
# warm check that API is up (lab gated, ignore result)
try:
    urllib.request.urlopen(r, timeout=20)
except Exception as e:
    print("lab endpoint:", str(e)[:80])

import urllib.request as u

for q in QUERIES:
    req = u.Request("http://localhost:8099/searches/nl",
                    data=json.dumps({"text": q, "limit": 2, "vision": False,
                                     "details": False, "benchmarks": False,
                                     "sources": ["kleinanzeigen"]}).encode(),
                    headers={"Content-Type": "application/json"})
    try:
        d = json.load(u.urlopen(req, timeout=300))
        p = d.get("parsed", {})
        print(f"Q: {q[:45]}")
        print(f"  -> keywords={p.get('keywords')!r} models={p.get('models', [])[:4]} "
              f"attrs={p.get('attributes', {})} results={len(d.get('results', []))}")
    except Exception as e:
        print(f"Q: {q[:45]} ERROR {str(e)[:100]}")

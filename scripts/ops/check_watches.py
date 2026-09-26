import urllib.request, json
from collections import Counter

m = json.load(urllib.request.urlopen("http://localhost:8099/metrics.json", timeout=30))
c = Counter()
for s in m.get("watchlist", []):
    c[s.get("keywords", "?")[:40]] += 1
print("watches:", len(m.get("watchlist", [])))
for k, n in c.most_common(15):
    print(f"  {n}x {k}")

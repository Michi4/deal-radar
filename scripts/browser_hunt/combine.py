#!/usr/bin/env python3
"""Combined ranking across eBay + kleinanzeigen + willhaben dumps."""
import json
import re
import sys

sys.path.insert(0, "/home/michi/hider/projects/deal-radar/packages")
sys.path.insert(0, "/home/michi/hider/projects/deal-radar/drivers")
from deal_radar.benchmarks import cached_cpu  # noqa: E402
from deal_radar.scoring import resolve_cpu_with_seeds  # noqa: E402

BAD = ("netzteil", "adapter", "ladeger", "kühl", "kuehl", "tastatur", "keyboard",
       "akku", "battery", "display", "bildschirm", "hülle", "huelle", "cover",
       "tasche", "bag", "kabel", "cable", "schrauben", "halterung", "ventilateur",
       "heatsink", "palmrest", "touchpad", "webcam", "speaker", "lautsprecher",
       "hinge", "bezel", "für teile", "fuer teile", "suche", "gesuche", "tausche",
       "defekt", "ersatzteile", "handauflage")


def num(s):
    s = (s or "").strip()
    if re.match(r"^\d{1,6}([.,]\d{1,3}){0,2}$", s):
        try:
            return float(s.replace(".", "").replace(",", "."))
        except ValueError:
            return None
    m = re.search(r"([\d.]+,\d{2}|\d+)", s)
    if m:
        try:
            return float(m.group(1).replace(".", "").replace(",", "."))
        except ValueError:
            return None
    return None


rows, seen = [], set()


def add(title, price, url, src):
    if not title or url in seen:
        return
    seen.add(url)
    tl = title.lower()
    if any(b in tl for b in BAD):
        return
    p = num(price)
    if not p or p <= 5 or p > 700:
        return
    cpu, conf, why, est, _ = resolve_cpu_with_seeds(title)
    if not cpu or conf < 0.85:
        return
    b = cached_cpu(cpu)
    multi = (b or {}).get("multi")
    if not multi:
        return
    # complete-system cost: bare boards need RAM+SSD (~125) before perf/€
    complete = bool(re.search(
        r"\b\d+\s*gb\b|laptop|notebook|macbook|mini[- ]?pc|desktop|komplett|"
        r"logic board|system", tl))
    up = 0 if complete else 125
    rows.append({"src": src, "title": title, "url": url, "price": p, "cpu": cpu,
                 "multi": multi, "up": up, "ppe": round(multi / (p + up), 1),
                 "est": est})


# eBay
import glob  # noqa: E402
for f in sorted(glob.glob("/tmp/opencode/hunt/mb[0-9]*.json")):
    try:
        d = json.load(open(f))
    except (FileNotFoundError, json.JSONDecodeError):
        continue
    if not isinstance(d, dict):
        continue
    for q, dd in d.items():
        if not isinstance(dd, dict):
            continue
        for c in dd.get("cards", []) or []:
            t = re.sub(r"Wird in neuem Fenster.*$", "", c.get("title", "")).strip()
            add(t, c.get("price", "").replace("EUR ", ""), c.get("url", ""), "ebay")

# kleinanzeigen
try:
    d = json.load(open("/tmp/opencode/hunt/ka2.json"))
    for q, dd in d.items():
        for c in dd.get("cards", []) or []:
            m = re.search(r"([\d.]+,\d{2}|\d+)\s*€", c.get("price") or "")
            add(c.get("title"), m.group(1) if m else "", c.get("url"), "kleinanzeigen")
except FileNotFoundError:
    pass

# willhaben
try:
    d = json.load(open("/tmp/opencode/hunt/wh1.json"))
    for q, dd in d.items():
        for c in dd.get("cards", []) or []:
            add(c.get("title"), c.get("price"), c.get("url"), "willhaben")
except FileNotFoundError:
    pass

# de-dup by url already handled; de-dup near-identical titles across sources
rows.sort(key=lambda r: (r["ppe"] * -1))
json.dump(rows, open("/tmp/opencode/hunt/combined.json", "w"),
          ensure_ascii=False, indent=1)
print(f"combined: {len(rows)} scored offers")
from collections import Counter  # noqa: E402
print("by source:", dict(Counter(r["src"] for r in rows)))
print()
print("=== TOP 40 perf/€ (all sources) ===")
for r in rows[:40]:
    print(f"{r['price']:.0f}EUR(+{r['up']}) ppe={r['ppe']:<7} {r['cpu']:<19} "
          f"{r['multi']:>6} [{r['src']}]")
    print(f"   {r['title'][:95]}")
    print(f"   {r['url']}")

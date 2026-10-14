#!/usr/bin/env python3
"""Full sweep ranking: clean boards + broken-display-usable + minis, all sources."""
import glob
import json
import re
import sys

sys.path.insert(0, "/home/michi/hider/projects/deal-radar/packages")
sys.path.insert(0, "/home/michi/hider/projects/deal-radar/drivers")
from deal_radar.benchmarks import cached_cpu  # noqa: E402
from deal_radar.scoring import resolve_cpu_with_seeds  # noqa: E402

HARD_BAD = ("netzteil", "adapter", "ladeger", "tastatur", "keyboard", "akku",
            "battery", "hülle", "huelle", "cover", "tasche", "bag", "kabel",
            "cable", "schrauben", "halterung", "ventilateur", "heatsink",
            "palmrest", "touchpad", "webcam", "speaker", "lautsprecher",
            "hinge", "bezel", "suche", "gesuche", "tausche", "handauflage",
            "ohne motherboard", "ohne mainboard")
# dead-board signals: NOT usable even headless
DEAD = ("mainboard defekt", "motherboard defekt", "logic board defekt",
        "platine defekt", "kein bild", "geht nicht an", "lässt sich nicht",
        "laesst sich nicht", "kein strom", "tot ", "wasserschaden",
        "für teile", "fuer teile", "ersatzteile", "teilespender",
        "bastlerware", "reparatur wie besehen")


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
broken_rows = []


def add(title, price, url, src):
    if not title or url in seen:
        return
    seen.add(url)
    tl = title.lower()
    if any(b in tl for b in HARD_BAD):
        return
    p = num(price)
    if not p or p <= 5 or p > 1200:
        return
    cpu, conf, why, est, _ = resolve_cpu_with_seeds(title)
    if not cpu or conf < 0.85:
        return
    b = cached_cpu(cpu)
    multi = (b or {}).get("multi")
    if not multi:
        return
    complete = bool(re.search(
        r"\b\d+\s*gb\b|laptop|notebook|macbook|mini[- ]?pc|desktop|komplett|"
        r"logic board|system|thinkpad|elitebook|probook|latitude|ideapad|"
        r"legion|pavilion|omen|victus|macbook|imac|nuc|tiny|micro\b", tl))
    up = 0 if complete else 125
    is_broken_display = bool(re.search(
        r"display\s*(defekt|schaden|bruch|gerissen|flackert|streifen)|"
        r"bildschirm\s*(defekt|schaden|bruch)|displaydefekt|"
        r"cracked\s*screen|broken\s*screen|screen\s*(broken|defect|issue)", tl))
    is_dead = any(d in tl for d in DEAD)
    rec = {"src": src, "title": title, "url": url, "price": p, "cpu": cpu,
           "multi": multi, "up": up, "ppe": round(multi / (p + up), 1),
           "est": est}
    if is_broken_display and not is_dead and complete:
        rec["broken"] = "display"
        broken_rows.append(rec)
        return
    if is_dead:
        return
    if any(x in tl for x in ("display", "bildschirm", "defekt")):
        # other defect kinds: keep out of the clean board
        return
    rows.append(rec)


for f in sorted(glob.glob("/tmp/opencode/hunt/mb[0-9]*.json")
                + glob.glob("/tmp/opencode/hunt/brk[0-9]*.json")
                + glob.glob("/tmp/opencode/hunt/mini[0-9]*.json")):
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

for fn, src in (("ka2", "kleinanzeigen"), ("ka3", "kleinanzeigen"),
                ("wh1", "willhaben"), ("wh2", "willhaben")):
    try:
        d = json.load(open(f"/tmp/opencode/hunt/{fn}.json"))
    except FileNotFoundError:
        continue
    for q, dd in d.items():
        for c in (dd.get("cards") or []):
            pr = c.get("price") or ""
            m = re.search(r"([\d.]+,\d{2}|\d+)\s*€", pr)
            pr = m.group(1) if m else pr
            add(c.get("title"), pr, c.get("url"), src)

rows.sort(key=lambda r: -r["ppe"])
broken_rows.sort(key=lambda r: -r["ppe"])
json.dump({"clean": rows, "broken_display": broken_rows},
          open("/tmp/opencode/hunt/combined2.json", "w"),
          ensure_ascii=False, indent=1)
from collections import Counter  # noqa: E402
print(f"clean: {len(rows)} | broken-display-usable: {len(broken_rows)}")
print("clean by source:", dict(Counter(r["src"] for r in rows)))
print("broken by source:", dict(Counter(r["src"] for r in broken_rows)))

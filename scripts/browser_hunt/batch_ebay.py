#!/usr/bin/env python3
"""Batch eBay searches via the debug browser. Polite: sequential + delays."""
import json
import os
import subprocess
import sys
import time

HUNT = "/tmp/opencode/hunt"
CDP = os.path.join(HUNT, "cdp.py")
CARDS = os.path.join(HUNT, "ebay_cards.js")

QUERIES = json.loads(sys.argv[1])
OUT = sys.argv[2]

results = {}
for i, q in enumerate(QUERIES, 1):
    slug = q.replace(" ", "_").replace("/", "-")[:40]
    url = ("https://www.ebay.at/sch/i.html?_nkw="
           + q.replace(" ", "+") + "&_sop=15&_ipg=60")
    try:
        p = subprocess.run([sys.executable, CDP, url, CARDS, "5000"],
                           capture_output=True, text=True, timeout=110)
        data = json.loads(p.stdout)
        results[q] = data
        print(f"[{i}/{len(QUERIES)}] {q!r}: {data.get('n', '?')} cards "
              f"(total {data.get('total','')[:30]})", flush=True)
    except Exception as e:
        print(f"[{i}/{len(QUERIES)}] {q!r}: FAIL {str(e)[:110]}", flush=True)
        results[q] = {"error": str(e)[:200]}
    time.sleep(4)  # polite gap

json.dump(results, open(OUT, "w"), ensure_ascii=False, indent=1)
print(f"\nwrote {OUT}: {len(results)} queries")

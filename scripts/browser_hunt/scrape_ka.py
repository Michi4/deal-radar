#!/usr/bin/env python3
"""kleinanzeigen.de scraper through the debug browser (CDP). Sequential only.

Structure (verified live): UL > LI > ARTICLE.flex justify-between > H3 > A[href]
with price in ARTICLE text as "320 € VB" / "1.299,99 €".
"""
import json
import os
import subprocess
import sys
import time

CDP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cdp.py")

JS = r"""
(() => {
  const out = [], seen = new Set();
  for (const li of document.querySelectorAll('li')) {
    const anchors = [...li.querySelectorAll('a[href*="/s-anzeige/"]')];
    let a = null, best = '';
    for (const cand of anchors) {
      const href = cand.getAttribute('href') || '';
      if (!/\/s-anzeige\/[^:?]+\/\d+/.test(href)) continue;
      const t = (cand.innerText || '').trim();
      if (t.length > best.length) { best = t; a = cand; }
    }
    if (!a || best.length < 8) continue;
    const href = a.getAttribute('href') || '';
    const art = li.querySelector('article');
    if (!art) continue;
    const txt = (art.innerText || '').replace(/\s+/g, ' ');
    // thousand-aware: (\d+)\s*€ matches the TAIL of "3.299 €" (-> "299 €").
    // Real bug, round 23. Always match the full thousand group first.
    const m = txt.match(/(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*€/);
    const title = best.replace(/\s+/g, ' ');
    if (title.length < 8) continue;
    const url = 'https://www.kleinanzeigen.de' + href;
    if (seen.has(url)) continue;
    seen.add(url);
    out.push({title: title.slice(0, 160),
              price: m ? m[0] : '',
              url: url,
              desc: txt.slice(0, 300)});
  }
  return {t: document.title.slice(0, 60), n: out.length, cards: out};
})()
"""


def main():
    queries = json.loads(sys.argv[1])
    out_path = sys.argv[2]
    results = {}
    for i, q in enumerate(queries, 1):
        slug = q.replace(" ", "-")
        url = f"https://www.kleinanzeigen.de/s-{slug}/k0?lernr=0&srchuntersorttype=nettoab"
        try:
            p = subprocess.run([sys.executable, CDP, url, JS, "6500"],
                               capture_output=True, text=True, timeout=100)
            data = json.loads(p.stdout)
            results[q] = data
            print(f"[{i}/{len(queries)}] {q!r}: {data.get('n', '?')} | "
                  f"{data.get('t', '')[:45]}", flush=True)
        except Exception as e:
            print(f"[{i}/{len(queries)}] {q!r}: FAIL {str(e)[:100]}", flush=True)
            results[q] = {"error": str(e)[:200]}
        time.sleep(5)

    json.dump(results, open(out_path, "w"), ensure_ascii=False, indent=1)
    print(f"\nwrote {out_path}: {len(results)} queries")


if __name__ == "__main__":
    main()

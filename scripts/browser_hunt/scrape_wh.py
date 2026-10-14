#!/usr/bin/env python3
"""willhaben.at scraper through the debug browser (CDP). Sequential only.

Structure (verified live): anchors a[href*="iad/kaufen-und-verkaufen/d/"] whose
inner text carries "<title> <price> € <shipping> <date>".
"""
import json
import re
import subprocess
import sys
import time

CDP = "/tmp/opencode/hunt/cdp.py"

JS = r"""
(async () => {
  // willhaben lazy-loads on scroll: 8 -> 33 anchors after scrolling
  for (let i = 0; i < 10; i++) {
    window.scrollBy(0, 1600);
    await new Promise(r => setTimeout(r, 900));
  }
  window.scrollTo(0, 0);
  await new Promise(r => setTimeout(r, 600));
  const out = [], seen = new Set();
  const sel = 'a[href*="iad/kaufen-und-verkaufen/d/"], a[href*="iad/kaufen-und-verkaufen/wien/"]';
  for (const a of document.querySelectorAll(sel)) {
    const href = a.getAttribute('href') || '';
    if (!/\/d\//.test(href) && !/\/wien\//.test(href)) continue;
    const txt = (a.innerText || '').replace(/\s+/g, ' ').trim();
    if (txt.length < 12) continue;
    // willhaben writes "€ 20" (euro first); eBay-style "20 €" also possible.
    const eidx = txt.indexOf('€');
    if (eidx < 0) continue;
    const win = txt.slice(Math.max(0, eidx - 14), eidx + 14);
    const m = win.match(/€\s*([\d.,]+)|([\d.,]+)\s*€/);
    const price = m ? (m[1] || m[2]) : '';
    // title = everything before the euro sign
    let title = txt.slice(0, eidx).replace(/\s*-\s*$/, '').trim();
    if (title.length < 8) continue;
    let url = href.startsWith('http') ? href : 'https://www.willhaben.at' + href;
    url = url.split('?')[0];
    if (seen.has(url)) continue;
    seen.add(url);
    out.push({title: title.slice(0, 160),
              price: price,
              url: url,
              raw: txt.slice(0, 260)});
  }
  return {t: document.title.slice(0, 60), n: out.length, cards: out};
})()
"""

def main():
    queries = json.loads(sys.argv[1])
    out_path = sys.argv[2]
    results = {}
    for i, q in enumerate(queries, 1):
        url = ("https://www.willhaben.at/iad/kaufen-und-verkaufen/marktplatz?keyword="
               + q.replace(" ", "%20") + "&rows=60&sort=0")
        try:
            p = subprocess.run([sys.executable, CDP, url, JS, "7500"],
                               capture_output=True, text=True, timeout=110)
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

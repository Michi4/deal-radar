#!/usr/bin/env python3
"""eBay item-page verifier: price + shipping + availability, all-in EUR.

Usage: python3 verify_items.py urls.txt  (one itm URL per line)
Writes JSON to stdout. Sequential, polite gaps. Single shared CDP tab.
"""
import json
import re
import subprocess
import sys
import time

CDP = "/tmp/opencode/hunt/cdp.py"
FX = 0.90  # USD->EUR incl VAT rule of thumb for AT cards

JS = r"""
(() => {
  const t = document.body.innerText.replace(/\s+/g, ' ');
  const h = ((document.querySelector('h1') || {}).innerText || '').trim();
  // price candidates
  let vals = [];
  for (const s of ['.x-price-primary span', '[itemprop=price]', '.notranslate']) {
    for (const e of document.querySelectorAll(s)) {
      const v = (e.textContent || '').trim();
      if (/[\d.,]+/.test(v) && v.length < 24) vals.push(v.slice(0, 22));
    }
  }
  vals = [...new Set(vals)];
  // shipping block — keep it LONG (numbers come after the method name)
  let ship = '';
  const sm = t.match(/(Versand|Shipping|Livraison)[^|]{0,160}/i);
  if (sm) ship = sm[0].slice(0, 170);
  const shipnum = (t.match(/(?:Versand|Shipping)[^$€|]{0,60}(US\s*\$|€)\s*([\d.,]+)/i) || [])[0] || '';
  const loc = (t.match(/Standort:\s*[^|]{0,40}/) || [''])[0].slice(0, 60);
  const qty = (t.match(/(\d+)\s*verfügbar|Only\s*(\d+)\s*left|(\d+)\s*available/i) || [])[0] || '';
  // SOLD detection must be strict: every page contains "Verkaufen" in nav and
  // "x verkauft" counters — only the ended-banner counts.
  const gone = /dieser Artikel ist (beendet|nicht mehr verfügbar)|this listing (has ended|is no longer available)|l'annonce est terminée/i.test(t);
  return JSON.stringify({h: h.slice(0, 90), vals: vals.slice(0, 6),
    ship: ship, shipnum: shipnum.slice(0, 40), loc: loc,
    gone: /dieser Artikel ist (beendet|nicht mehr verfügbar)|this listing (has ended|is no longer available)/i.test(t)});
})()
"""


def _de_num(num: str) -> float | None:
    """German-format number: 1.245,74 -> 1245.74; 44,65 -> 44.65; 1.300 -> 1300."""
    try:
        num = num.strip()
        if "." in num and "," in num:
            return float(num.replace(".", "").replace(",", "."))
        if "," in num:
            head, _, tail = num.rpartition(",")
            if len(tail) == 2:
                return float(head.replace(".", "") + "." + tail)
            return float(num.replace(",", "").replace(".", ""))
        return float(num.replace(".", "") if num.count(".") > 1
                     else (num if "." not in num or len(num.rsplit(".", 1)[1]) != 3
                           else num.replace(".", "")))
    except ValueError:
        return None


def ship_eur_of(ship_text):
    """Shipping cost from the item-page shipping blurb. Prefer the parenthesized
    '(ca. EUR x)' figure — that is what an AT buyer actually pays. Fall back to
    the US$ figure. 'Kostenlos' = 0. (Round 21: a truncated shipnum match was
    truthy garbage that shadowed the good parse — parse `ship` directly.)
    """
    import re as _re
    if not ship_text:
        return None
    if _re.search(r"kostenlos|free shipping|gratis", ship_text, _re.I):
        return 0.0
    m = _re.search(r"\(\s*ca\.\s*EUR\s*([\d.,]+)\s*\)", ship_text)
    if m:
        return _de_num(m.group(1))
    m = _re.search(r"US\s*\$\s*([\d.,]+)", ship_text)
    if m:
        num = m.group(1)
        if "," in num and "." not in num:
            num = num.replace(",", ".")
        else:
            num = num.replace(",", "")
        try:
            return round(float(num) * FX, 2)
        except ValueError:
            return None
    return None


def eur_of(s):
    """EUR figure or USD->EUR. (Round 21 postmortem: USD '115,89' hit
    float('11589') x 0.9 = 10430 — the comma branch below fixes it.)"""
    if not s:
        return None
    m = re.search(r"([\d.,]+)\s*€|€\s*([\d.,]+)", s)
    if m:
        return _de_num(m.group(1) or m.group(2))
    # 'EUR 1.245,74' / 'ca. EUR 44,65' — no € glyph, EUR prefix instead
    m = re.search(r"EUR\s*([\d.,]+)", s)
    if m:
        return _de_num(m.group(1))
    m = re.search(r"US\s*\$\s*([\d.,]+)", s)
    if m:
        num = m.group(1)
        if "," in num and "." in num:
            if num.rfind(",") > num.rfind("."):
                num = num.replace(".", "").replace(",", ".")  # DE-render: 1.899,00
            else:
                num = num.replace(",", "")  # US thousands: 1,395.10
        elif "," in num:
            num = num.replace(",", ".")  # German-rendered decimal: 115,89
        try:
            return round(float(num) * FX, 2)
        except ValueError:
            return None
    return None


def main():
    urls = [l.strip() for l in open(sys.argv[1]) if "/itm/" in l]
    out = []
    for i, u in enumerate(urls, 1):
        try:
            p = subprocess.run([sys.executable, CDP, u, JS, "7000"],
                               capture_output=True, text=True, timeout=100)
            d = json.loads(p.stdout)
            price = None
            for v in d.get("vals", []):
                price = eur_of(v)
                if price:
                    break
            shp = ship_eur_of(d.get("ship", ""))
            # "Kostenloser Versand" / free shipping
            if re.search(r"kostenlos|free shipping|gratis", d.get("ship", ""), re.I):
                shp = 0.0
            d["price_eur"] = price
            d["ship_eur"] = shp
            d["total_eur"] = round(price + shp, 2) if price and shp is not None else price
            d["url"] = u
            out.append(d)
            print(f"[{i}/{len(urls)}] {d.get('total_eur')} all-in | "
                  f"{(d.get('h') or '')[:60]}", flush=True)
        except Exception as e:
            print(f"[{i}/{len(urls)}] FAIL {u[-14:]} {str(e)[:90]}", flush=True)
            out.append({"url": u, "error": str(e)[:150]})
        time.sleep(3)
    json.dump(out, open("/tmp/opencode/hunt/verified.json", "w"),
              ensure_ascii=False, indent=1)
    print("wrote /tmp/opencode/hunt/verified.json")


if __name__ == "__main__":
    main()

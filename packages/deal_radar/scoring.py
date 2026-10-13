"""Value scoring + enrichment fabric. Generic: works for any entity, not just deals."""
from __future__ import annotations

import re

from .contracts import CanonicalListing, EnrichmentFact, Evidence, FactStatus

# tiny built-in CPU benchmark DB (enrichment plugin example; replace with real source)
CPU_DB = {
    "ryzen 5 5600h": 16500, "ryzen 7 5800h": 19500, "ryzen 7 6800u": 19800,
    "ryzen 7 pro 6850u": 20500, "i7-12700h": 24000, "i7-11800h": 19000,
    "m1": 17500, "m2": 19500, "m3": 23000, "i5-1135g7": 13500,
}

# model family -> candidate CPUs (seed knowledge; AI extends per query, cached on disk)
MODEL_CPU_SEED = {
    "hp elitebook 845 g8": ["Ryzen 5 PRO 5650U", "Ryzen 7 PRO 5850U"],
    "hp 835 g8": ["Ryzen 5 PRO 5650U", "Ryzen 7 PRO 5850U"],
    "hp elitebook 840 g8": ["i5-1135G7", "i7-1165G7"],
    "hp elitebook 840 g9": ["i5-1235U", "i7-1255U"],
    "thinkpad t14 gen 2": ["Ryzen 5 PRO 5650U", "Ryzen 7 PRO 5850U", "i5-1135G7", "i7-1165G7"],
    "thinkpad t480": ["i5-8250U", "i7-8550U"],
    "thinkpad t490": ["i5-8265U", "i7-8565U"],
    "thinkpad x1 carbon gen 6": ["i5-8350U", "i7-8650U"],
    "thinkpad x1 carbon gen 5": ["i5-7200U", "i5-7300U", "i7-7500U", "i7-7600U"],    "thinkpad x1 carbon gen 7": ["i5-8265U", "i7-8565U"],
    "thinkpad x1 carbon gen 8": ["i5-10210U", "i7-10610U"],
    "thinkpad x1 carbon gen 9": ["i5-1135G7", "i7-1165G7"],
    "thinkpad x1 yoga gen 4": ["i5-8265U", "i7-8565U"],
    "macbook air m1": ["M1"],
    "macbook air m2": ["M2"],
    "macbook pro m1": ["M1", "M1 Pro", "M1 Max"],
    "macbook pro m2": ["M2", "M2 Pro", "M2 Max"],
}

# lineup expansion: business lines by model x generation. Labeled estimates only
# (conf 0.45 + alternatives in the drawer) — listings that name just "i7" or
# "Ryzen 7" resolve to the real factory options instead of honest-unknown.
MODEL_CPU_SEED.update({
    # ThinkPad X1 Carbon
    "thinkpad x1 carbon gen 3": ["i5-5200U", "i5-5300U", "i7-5500U", "i7-5600U"],
    "thinkpad x1 carbon gen 4": ["i5-6200U", "i5-6300U", "i7-6500U", "i7-6600U"],
    "x1 carbon gen 3": ["i5-5200U", "i5-5300U", "i7-5500U", "i7-5600U"],
    "x1 carbon gen 4": ["i5-6200U", "i5-6300U", "i7-6500U", "i7-6600U"],
    "x1 carbon gen 6": ["i5-8250U", "i5-8350U", "i7-8550U", "i7-8650U"],
    "x1 carbon gen 7": ["i5-8265U", "i5-8365U", "i7-8565U", "i7-8665U"],
    "thinkpad x1 carbon gen 7": ["i5-8265U", "i5-8365U", "i7-8565U", "i7-8665U"],
    "x1 carbon gen 8": ["i5-10210U", "i5-10310U", "i7-10510U", "i7-10610U", "i7-10710U"],
    "thinkpad x1 carbon gen 8": ["i5-10210U", "i5-10310U", "i7-10510U", "i7-10610U", "i7-10710U"],
    "x1 carbon gen 9": ["i5-1135G7", "i5-1145G7", "i7-1165G7", "i7-1185G7"],
    "thinkpad x1 carbon gen 9": ["i5-1135G7", "i5-1145G7", "i7-1165G7", "i7-1185G7"],
    "x1 carbon gen 10": ["i5-1235U", "i5-1240P", "i7-1255U", "i7-1260P", "i7-1270P", "i7-1280P"],
    "thinkpad x1 carbon gen 10": ["i5-1235U", "i5-1240P", "i7-1255U", "i7-1260P", "i7-1270P"],
    "x1 carbon gen 11": ["i5-1335U", "i5-1345U", "i7-1355U", "i7-1365U", "i7-1370P"],
    "thinkpad x1 carbon gen 11": ["i5-1335U", "i5-1345U", "i7-1355U", "i7-1365U"],
    "x1 carbon gen 12": ["Core Ultra 5 125U", "Core Ultra 7 155U", "Core Ultra 7 165U"],
    "thinkpad x1 carbon gen 12": ["Core Ultra 5 125U", "Core Ultra 7 155U", "Core Ultra 7 165U"],
    "x1 carbon gen 13": ["Core Ultra 5 225V", "Core Ultra 7 255V", "Core Ultra 7 258V"],
    # ThinkPad X1 Yoga
    "x1 yoga gen 2": ["i5-7200U", "i5-7300U", "i7-7500U", "i7-7600U"],
    "thinkpad x1 yoga gen 2": ["i5-7200U", "i5-7300U", "i7-7500U", "i7-7600U"],
    "x1 yoga gen 3": ["i5-8250U", "i5-8350U", "i7-8550U", "i7-8650U"],
    "thinkpad x1 yoga gen 3": ["i5-8250U", "i5-8350U", "i7-8550U", "i7-8650U"],
    "x1 yoga gen 4": ["i5-8265U", "i7-8565U", "i7-8665U"],
    "x1 yoga gen 5": ["i5-10210U", "i7-10510U", "i7-10710U"],
    "thinkpad x1 yoga gen 5": ["i5-10210U", "i7-10510U", "i7-10710U"],
    "x1 yoga gen 6": ["i5-1135G7", "i7-1165G7", "i7-1185G7"],
    "thinkpad x1 yoga gen 6": ["i5-1135G7", "i7-1165G7", "i7-1185G7"],
    "x1 yoga gen 7": ["i5-1235U", "i5-1240P", "i7-1255U", "i7-1260P", "i7-1270P"],
    "thinkpad x1 yoga gen 7": ["i5-1235U", "i5-1240P", "i7-1255U", "i7-1260P"],
    "x1 yoga gen 8": ["i5-1335U", "i7-1355U", "i7-1365U"],
    "thinkpad x1 yoga gen 8": ["i5-1335U", "i7-1355U", "i7-1365U"],
    "x1 yoga g8": ["i5-1335U", "i7-1355U", "i7-1365U"],
    "x1 yoga g7": ["i5-1235U", "i5-1240P", "i7-1255U", "i7-1260P"],
    "x1 yoga g6": ["i5-1135G7", "i7-1165G7", "i7-1185G7"],
    # ThinkPad T14 / T14s
    "t14 gen 1": ["i5-10210U", "i5-10310U", "i7-10510U", "i7-10610U", "Ryzen 5 PRO 4650U", "Ryzen 7 PRO 4750U"],
    "thinkpad t14 gen 1": ["i5-10210U", "i7-10510U", "Ryzen 5 PRO 4650U", "Ryzen 7 PRO 4750U"],
    "t14 gen 2": ["i5-1135G7", "i7-1165G7", "Ryzen 5 PRO 5650U", "Ryzen 7 PRO 5850U"],
    "t14 gen 3": ["i5-1235U", "i5-1240P", "i7-1255U", "i7-1260P", "Ryzen 5 PRO 7530U", "Ryzen 7 PRO 7730U", "Ryzen 7 PRO 7735U"],
    "thinkpad t14 gen 3": ["i5-1235U", "i7-1255U", "Ryzen 5 PRO 7530U", "Ryzen 7 PRO 7735U"],
    "t14 gen 4": ["i5-1335U", "i7-1355U", "Ryzen 5 PRO 7530U", "Ryzen 7 PRO 7735U"],
    "thinkpad t14 gen 4": ["i5-1335U", "i7-1355U", "Ryzen 5 PRO 7530U", "Ryzen 7 PRO 7735U"],
    "t14 gen 5": ["Core Ultra 5 125U", "Core Ultra 7 155U", "Ryzen 5 PRO 8540U", "Ryzen 7 PRO 8640U"],
    "t14s gen 1": ["i5-10210U", "i7-10510U", "i7-10610U", "Ryzen 5 PRO 4650U", "Ryzen 7 PRO 4750U"],
    "thinkpad t14s gen 1": ["i5-10210U", "i7-10510U", "Ryzen 5 PRO 4650U", "Ryzen 7 PRO 4750U"],
    "t14s gen 2": ["i5-1145G7", "i7-1165G7", "i7-1185G7", "Ryzen 5 PRO 5650U", "Ryzen 7 PRO 5850U"],
    "thinkpad t14s gen 2": ["i5-1145G7", "i7-1165G7", "Ryzen 5 PRO 5650U", "Ryzen 7 PRO 5850U"],
    "t14s gen 3": ["i5-1240P", "i7-1260P", "i7-1270P", "i7-1280P", "Ryzen 7 PRO 6850U"],
    "thinkpad t14s gen 3": ["i5-1240P", "i7-1260P", "Ryzen 7 PRO 6850U"],
    "t14s gen 4": ["i5-1335U", "i7-1355U", "i7-1365U", "Ryzen 5 PRO 7540U", "Ryzen 7 PRO 7840U"],
    "thinkpad t14s gen 4": ["i5-1335U", "i7-1355U", "Ryzen 5 PRO 7540U"],
    "t14s gen 5": ["Core Ultra 5 125U", "Core Ultra 7 155U", "Core Ultra 7 165U"],
    "thinkpad t14s gen 5": ["Core Ultra 5 125U", "Core Ultra 7 155U", "Core Ultra 7 165U"],
    # ThinkPad X13
    "x13 gen 1": ["i5-10210U", "i7-10510U", "i7-10710U", "Ryzen 5 PRO 4650U", "Ryzen 7 PRO 4750U"],
    "thinkpad x13 gen 1": ["i5-10210U", "i7-10510U", "Ryzen 5 PRO 4650U", "Ryzen 7 PRO 4750U"],
    "x13 gen 2": ["i5-1145G7", "i7-1165G7", "Ryzen 5 PRO 5650U", "Ryzen 7 PRO 5850U"],
    "thinkpad x13 gen 2": ["i5-1145G7", "i7-1165G7", "Ryzen 5 PRO 5650U", "Ryzen 7 PRO 5850U"],
    "x13 gen 3": ["i5-1240P", "i5-1250P", "i7-1260P", "Ryzen 7 PRO 6850U"],
    "x13 gen 4": ["i5-1335U", "i7-1355U", "Ryzen 5 PRO 7540U", "Ryzen 7 PRO 7640U"],
    "thinkpad x13 gen 4": ["i5-1335U", "i7-1355U", "Ryzen 5 PRO 7540U"],
    "x13 gen 5": ["Core Ultra 5 125U", "Core Ultra 7 155U", "Core Ultra 7 165U"],
    # ThinkPad T-series classics
    "thinkpad t480": ["i5-8250U", "i5-8350U", "i7-8550U", "i7-8650U"],
    "thinkpad t480s": ["i5-8250U", "i5-8350U", "i7-8550U", "i7-8650U"],
    "thinkpad t580": ["i5-8250U", "i5-8350U", "i7-8550U", "i7-8650U"],
    "thinkpad t490": ["i5-8265U", "i5-8365U", "i7-8565U", "i7-8665U"],
    "thinkpad t590": ["i5-8265U", "i7-8565U", "i7-8665U", "i7-9750H", "i7-9850H"],
    "thinkpad t570": ["i5-7200U", "i5-7300U", "i7-7500U", "i7-7600U"],
    "thinkpad t560": ["i5-6200U", "i5-6300U", "i7-6500U", "i7-6600U"],
    "thinkpad t550": ["i5-5200U", "i5-5300U", "i7-5500U", "i7-5600U"],
    "thinkpad t460": ["i5-6200U", "i5-6300U", "i7-6500U", "i7-6600U"],
    "thinkpad t470": ["i5-7200U", "i5-7300U", "i7-7500U", "i7-7600U"],
    "thinkpad t460s": ["i5-6200U", "i5-6300U", "i7-6500U", "i7-6600U"],
    "thinkpad t470s": ["i5-7200U", "i5-7300U", "i7-7500U", "i7-7600U"],
    "thinkpad t460p": ["i5-6300HQ", "i5-6440HQ", "i7-6820HQ"],
    "thinkpad t470p": ["i5-7300HQ", "i7-7820HQ"],
    # bare T-series classics (vinted titles often drop the "ThinkPad" prefix:
    # "Lenovo T460 ..."). Same candidates as the prefixed keys above.
    "t460": ["i5-6200U", "i5-6300U", "i7-6500U", "i7-6600U"],
    "t470": ["i5-7200U", "i5-7300U", "i7-7500U", "i7-7600U"],
    "t480": ["i5-8250U", "i5-8350U", "i7-8550U", "i7-8650U"],
    "t490": ["i5-8265U", "i5-8365U", "i7-8565U", "i7-8665U"],
    "t580": ["i5-8250U", "i5-8350U", "i7-8550U", "i7-8650U"],
    "t590": ["i5-8265U", "i7-8565U", "i7-8665U", "i7-9750H", "i7-9850H"],
    "t560": ["i5-6200U", "i5-6300U", "i7-6500U", "i7-6600U"],
    "t570": ["i5-7200U", "i5-7300U", "i7-7500U", "i7-7600U"],
    "t550": ["i5-5200U", "i5-5300U", "i7-5500U", "i7-5600U"],
    # ThinkPad X-series classics (X250: Broadwell; X260/X270: Skylake/Kaby Lake;
    # X280: Kaby Lake-R)
    "thinkpad x250": ["i5-5200U", "i5-5300U", "i7-5600U"],
    "x250": ["i5-5200U", "i5-5300U", "i7-5600U"],
    "thinkpad x260": ["i5-6200U", "i5-6300U", "i7-6500U", "i7-6600U"],
    "x260": ["i5-6200U", "i5-6300U", "i7-6500U", "i7-6600U"],
    "thinkpad x270": ["i5-6200U", "i5-6300U", "i5-7200U", "i5-7300U", "i7-7500U", "i7-7600U"],
    "x270": ["i5-6200U", "i5-6300U", "i5-7200U", "i5-7300U", "i7-7500U", "i7-7600U"],
    "thinkpad x280": ["i5-8250U", "i5-8350U", "i7-8550U", "i7-8650U"],
    "x280": ["i5-8250U", "i5-8350U", "i7-8550U", "i7-8650U"],
    # ThinkPad X1 Extreme (Gen 1: 8750H/8850H; Gen 2: 9750H/9850H; Gen 3: 10750H/10850H;
    # Gen 4: 11800H/11950H; Gen 5: 12700H/12800H/12900H)
    "x1 extreme gen 1": ["i5-8400H", "i7-8750H", "i7-8850H", "Xeon E-2176M"],
    "thinkpad x1 extreme gen 1": ["i5-8400H", "i7-8750H", "i7-8850H", "Xeon E-2176M"],
    "x1 extreme gen 2": ["i5-9400H", "i7-9750H", "i7-9850H", "i9-9880H", "Xeon E-2276M"],
    "thinkpad x1 extreme gen 2": ["i5-9400H", "i7-9750H", "i7-9850H", "i9-9880H"],
    "x1 extreme gen 3": ["i5-10400H", "i7-10750H", "i7-10850H", "i9-10885H", "Xeon W-10855M"],
    "thinkpad x1 extreme gen 3": ["i5-10400H", "i7-10750H", "i7-10850H", "i9-10885H"],
    "x1 extreme gen 4": ["i7-11800H", "i9-11950H", "i9-11980HK"],
    "thinkpad x1 extreme gen 4": ["i7-11800H", "i9-11950H", "i9-11980HK"],
    "x1 extreme gen 5": ["i7-12700H", "i7-12800H", "i9-12900H"],
    "thinkpad x1 extreme gen 5": ["i7-12700H", "i7-12800H", "i9-12900H"],
    # Legion Y-gaming (Y520: Kaby Lake-H; Y540-15/17IRH: Coffee Lake-H Refresh)
    "legion y520": ["i5-7300HQ", "i7-7700HQ"],
    "legion y540": ["i5-9300H", "i7-9750H", "i7-9750HF"],
    "legion y540-15irh": ["i5-9300H", "i7-9750H"],
    "legion y540-17irh": ["i5-9300H", "i7-9750H"],
    "legion y545": ["i5-9300H", "i7-9750H"],
    "legion y7000": ["i5-8300H", "i7-8750H"],
    "legion y730": ["i5-8300H", "i7-8750H"],
    "t15 gen 1": ["i5-10210U", "i5-10310U", "i7-10510U", "i7-10610U", "i7-10710U"],
    "thinkpad t15 gen 1": ["i5-10210U", "i7-10510U", "i7-10710U"],
    "t15 gen 2": ["i5-1135G7", "i7-1165G7", "i7-1185G7"],
    "t16 gen 1": ["i5-1245U", "i5-1255U", "i7-1260P", "i7-1270P", "Ryzen 5 PRO 7530U", "Ryzen 7 PRO 7730U"],
    "t16 gen 2": ["i5-1335U", "i7-1355U", "i7-1365U", "Ryzen 5 PRO 7540U"],
    # ThinkPad E/L/A lines
    "thinkpad e14 gen 2": ["i5-1135G7", "i7-1165G7", "Ryzen 5 4500U", "Ryzen 7 4700U"],
    "e14 gen 2": ["i5-1135G7", "Ryzen 5 4500U", "Ryzen 7 4700U"],
    "thinkpad e14 gen 3": ["i5-1135G7", "i7-1165G7", "Ryzen 5 5500U", "Ryzen 7 5700U"],
    "e14 gen 3": ["i5-1135G7", "Ryzen 5 5500U", "Ryzen 7 5700U"],
    "thinkpad e14 gen 4": ["i5-1235U", "i7-1255U", "Ryzen 5 7530U", "Ryzen 7 7730U"],
    "e14 gen 4": ["i5-1235U", "Ryzen 5 7530U", "Ryzen 7 7730U"],
    "thinkpad e14 gen 5": ["i5-1335U", "i7-1355U", "Ryzen 5 7530U", "Ryzen 7 7730U"],
    "thinkpad e15 gen 2": ["i5-1135G7", "i7-1165G7", "Ryzen 5 4500U", "Ryzen 7 4700U"],
    "thinkpad e15 gen 3": ["i5-1135G7", "Ryzen 5 5500U", "Ryzen 7 5700U"],
    "thinkpad e15 gen 4": ["i5-1235U", "Ryzen 5 7530U", "Ryzen 7 7730U"],
    "e495": ["Ryzen 3 3200U", "Ryzen 5 3500U", "Ryzen 7 3700U"],
    "e595": ["Ryzen 3 3200U", "Ryzen 5 3500U", "Ryzen 7 3700U"],
    "t495": ["Ryzen 5 PRO 3500U", "Ryzen 7 PRO 3700U"],
    "t495s": ["Ryzen 5 PRO 3500U", "Ryzen 7 PRO 3700U"],
    "a485": ["Ryzen 5 PRO 2500U", "Ryzen 7 PRO 2700U"],
    "thinkpad l14 gen 1": ["i5-10210U", "i7-10510U", "Ryzen 5 PRO 4650U"],
    "l14 gen 1": ["i5-10210U", "Ryzen 5 PRO 4650U"],
    "thinkpad l14 gen 2": ["i5-1135G7", "i7-1165G7", "Ryzen 5 PRO 5650U", "Ryzen 7 PRO 5850U"],
    "l14 gen 2": ["i5-1135G7", "Ryzen 5 PRO 5650U", "Ryzen 7 PRO 5850U"],
    "thinkpad l14 gen 3": ["i5-1235U", "Ryzen 5 PRO 7530U", "Ryzen 7 PRO 7730U"],
    "thinkpad l14 gen 4": ["i5-1335U", "i7-1355U", "Ryzen 5 PRO 7530U"],
    "thinkpad l15 gen 1": ["i5-10210U", "i7-10510U", "Ryzen 5 PRO 4650U"],
    "thinkpad l15 gen 2": ["i5-1135G7", "Ryzen 5 PRO 5650U"],
    "thinkpad l13 yoga gen 2": ["i5-10210U", "i7-10510U", "i7-10710U"],
    "thinkpad l13 yoga gen 3": ["i5-1135G7", "i7-1165G7"],
    "thinkpad l13 yoga gen 4": ["i5-1335U", "i7-1355U", "Ryzen 5 PRO 7530U"],
    "thinkpad x390": ["i5-8265U", "i5-8365U", "i7-8565U"],
    "x390": ["i5-8265U", "i7-8565U"],
    "thinkpad x395": ["Ryzen 3 PRO 3300U", "Ryzen 5 PRO 3500U", "Ryzen 7 PRO 3700U"],
    "x395": ["Ryzen 5 PRO 3500U", "Ryzen 7 PRO 3700U"],
    # ThinkPad P-series mobile workstations
    "thinkpad p15 gen 1": ["i7-10750H", "i7-10850H", "i9-10980HK", "Xeon W-10855M"],
    "p15 gen 1": ["i7-10750H", "i7-10850H", "i9-10980HK"],
    "thinkpad p15s gen 1": ["i5-10300H", "i7-10500H", "i7-10700H", "i7-10800H"],
    "thinkpad p15s gen 2": ["i5-11300H", "i7-11500H", "i7-11800H"],
    "thinkpad p16s gen 1": ["i7-12700H", "i7-12800H", "Ryzen 7 PRO 6850H"],
    "p16s gen 1": ["i7-12700H", "i7-12800H", "Ryzen 7 PRO 6850H"],
    "thinkpad p16s gen 2": ["i7-13700H", "i7-13800H"],
    "thinkpad p16 gen 1": ["i7-12700H", "i7-12800H", "i9-12950HX"],
    "thinkpad p16 gen 2": ["i7-13700HX", "i9-13950HX"],
    "thinkpad p1 gen 4": ["i7-11800H", "i9-11950H", "Xeon W-11855M"],
    "thinkpad p14s gen 1": ["i5-10210U", "i7-10510U", "i7-10710U", "Ryzen 7 PRO 4750U"],
    "p14s gen 1": ["i5-10210U", "i7-10510U", "Ryzen 7 PRO 4750U"],
    "thinkpad p14s gen 2": ["i5-1145G7", "i7-1165G7", "Ryzen 7 PRO 5850U"],
    "thinkpad p14s gen 3": ["i5-1240P", "i7-1260P", "i7-1280P", "Ryzen 7 PRO 6850U"],
    "thinkpad p14s gen 4": ["i5-1355U", "i7-1365U", "i7-1370P", "Ryzen 7 PRO 7840U"],
    "thinkpad p50": ["i7-6700HQ", "i7-6820HQ", "i7-7300HQ", "i7-7820HQ", "Xeon E3-1505M"],
    "thinkpad p51": ["i7-7300HQ", "i7-7820HQ", "Xeon E3-1505M"],
    "thinkpad p51s": ["i5-6200U", "i5-6300U", "i7-7500U", "i7-7600U"],
    "thinkpad p52s": ["i5-8250U", "i5-8350U", "i7-8550U", "i7-8650U"],
    "thinkpad p52": ["i7-8750H", "i7-8850H", "i9-8950HK", "Xeon E-2176M"],
    "thinkpad p53": ["i7-9750H", "i7-9850H", "Xeon E-2276M"],
    # Dell Latitude
    "latitude 3400": ["i5-8265U", "i7-8565U"],
    "latitude 3410": ["i5-10210U", "i7-10510U"],
    "latitude 3420": ["i5-1135G7", "i7-1165G7", "i7-1185G7"],
    "latitude 3430": ["i5-1235U", "i7-1255U"],
    "latitude 3440": ["i5-1335U", "i7-1355U"],
    "latitude 3450": ["Core Ultra 5 125U", "Core Ultra 7 155U"],
    "latitude 3500": ["i5-8265U", "i7-8565U"],
    "latitude 3510": ["i5-10210U", "i7-10510U", "i7-10710U"],
    "latitude 3520": ["i5-1135G7", "i7-1165G7"],
    "latitude 3530": ["i5-1235U", "i5-1240P", "i7-1255U", "i7-1260P"],
    "latitude 3540": ["i5-1335U", "i7-1355U"],
    "latitude 3550": ["Core Ultra 5 125U", "Core Ultra 7 155U"],
    "latitude 5400": ["i5-8265U", "i5-8365U", "i7-8565U"],
    "latitude 5410": ["i5-10210U", "i7-10510U", "i7-10710U"],
    "latitude 5420": ["i5-1135G7", "i5-1145G7", "i7-1165G7", "i7-1185G7"],
    "latitude 5430": ["i5-1235U", "i5-1240P", "i7-1255U", "i7-1260P"],
    "latitude 5440": ["i5-1335U", "i5-1345U", "i7-1355U", "i7-1365U"],
    "latitude 5450": ["Core Ultra 5 125U", "Core Ultra 7 155U", "Core Ultra 7 165U"],
    "latitude 5500": ["i5-8265U", "i7-8565U"],
    "latitude 5510": ["i5-10210U", "i7-10710U"],
    "latitude 5520": ["i5-1135G7", "i7-1165G7", "i7-1185G7"],
    "latitude 5530": ["i5-1235U", "i7-1255U", "i7-1270P"],
    "latitude 5540": ["i5-1335U", "i7-1355U", "i7-1365U"],
    "latitude 5550": ["Core Ultra 5 125U", "Core Ultra 7 155U", "Core Ultra 7 165U"],
    "latitude 5300": ["i5-8265U", "i7-8565U"],
    "latitude 5310": ["i5-10210U", "i7-10510U"],
    "latitude 5320": ["i5-1135G7", "i7-1165G7"],
    "latitude 5330": ["i5-1235U", "i7-1255U", "i7-1260P", "Ryzen 5 PRO 7530U"],
    "latitude 5340": ["i5-1335U", "i7-1355U"],
    "latitude 5350": ["Core Ultra 5 125U", "Core Ultra 7 155U", "Core Ultra 7 165U"],
    "latitude 7300": ["i5-8250U", "i7-8550U"],
    "latitude 7310": ["i5-10210U", "i7-10510U"],
    "latitude 7320": ["i5-1135G7", "i7-1165G7"],
    "latitude 7330": ["i5-1235U", "i7-1255U"],
    "latitude 7340": ["i5-1335U", "i7-1355U"],
    "latitude 7350": ["Core Ultra 5 125U", "Core Ultra 7 155U", "Core Ultra 7 165U"],
    "latitude 7400": ["i5-8265U", "i5-8365U", "i7-8565U"],
    "latitude 7410": ["i5-10210U", "i7-10510U", "i7-10710U"],
    "latitude 7420": ["i5-1135G7", "i5-1145G7", "i7-1165G7", "i7-1185G7"],
    "latitude 7430": ["i5-1235U", "i5-1240P", "i7-1255U", "i7-1260P"],
    "latitude 7440": ["i5-1335U", "i5-1345U", "i7-1355U", "i7-1365U"],
    "latitude 7450": ["Core Ultra 5 125U", "Core Ultra 7 155U", "Core Ultra 7 165U"],
    "latitude e7470": ["i5-6200U", "i5-6300U", "i7-6600U"],
    "latitude e7480": ["i5-7200U", "i5-7300U", "i7-7500U", "i7-7600U"],
    "latitude e7490": ["i5-8250U", "i5-8350U", "i7-8550U", "i7-8650U"],
    "latitude e5470": ["i5-6200U", "i5-6300U", "i5-6440HQ", "i7-6820HQ"],
    "latitude e5480": ["i5-8250U", "i5-8350U", "i7-8550U"],
    "latitude e5490": ["i5-8250U", "i5-8350U", "i7-8550U", "i7-8650U"],
    "latitude e5491": ["i5-8300H", "i5-8400H", "i7-8750H"],
    "latitude e5570": ["i5-6300U", "i5-6440HQ", "i7-6820HQ"],
    "latitude e5580": ["i5-7300HQ", "i7-7820HQ"],
    "latitude e5590": ["i5-8250U", "i7-8550U"],
    "latitude e5591": ["i5-8300H", "i7-8750H"],
    "latitude 7280": ["i5-7200U", "i5-7300U", "i7-7500U", "i7-7600U"],
    "latitude 7290": ["i5-8265U", "i5-8365U", "i7-8565U"],
    "latitude 3300": ["i5-8265U", "i7-8565U"],
    # HP EliteBook / ProBook / ZBook
    "elitebook 830 g5": ["i5-7200U", "i5-7300U", "i7-7500U", "i5-8250U", "i7-8550U"],
    "elitebook 840 g5": ["i5-7200U", "i5-7300U", "i7-7500U", "i5-8250U", "i7-8550U"],
    "elitebook 830 g6": ["i5-8265U", "i5-8365U", "i7-8565U"],
    "elitebook 840 g6": ["i5-8265U", "i5-8365U", "i7-8565U"],
    "elitebook 830 g7": ["i5-10210U", "i5-10310U", "i7-10510U", "i7-10610U"],
    "elitebook 840 g7": ["i5-10210U", "i5-10310U", "i7-10510U", "i7-10610U"],
    "elitebook 830 g8": ["i5-1135G7", "i5-1145G7", "i7-1165G7", "i7-1185G7"],
    "hp elitebook 830 g8": ["i5-1135G7", "i5-1145G7", "i7-1165G7", "i7-1185G7"],
    "elitebook 840 g8": ["i5-1135G7", "i7-1165G7"],
    "elitebook 830 g9": ["i5-1235U", "i5-1240P", "i7-1255U", "i7-1260P"],
    "elitebook 840 g9": ["i5-1235U", "i5-1240P", "i7-1255U", "i7-1260P"],
    "elitebook 830 g10": ["i5-1335U", "i5-1345U", "i7-1355U", "i7-1365U"],
    "elitebook 840 g10": ["i5-1335U", "i5-1345U", "i7-1355U", "i7-1365U"],
    "elitebook 830 g11": ["Core Ultra 5 125U", "Core Ultra 7 155U", "Core Ultra 7 165U"],
    "elitebook 840 g11": ["Core Ultra 5 125U", "Core Ultra 7 155U", "Core Ultra 7 165U"],
    "elitebook 835 g7": ["Ryzen 5 PRO 4650U", "Ryzen 7 PRO 4750U"],
    "elitebook 845 g7": ["Ryzen 5 PRO 4650U", "Ryzen 7 PRO 4750U"],
    "elitebook 835 g8": ["Ryzen 5 PRO 5650U", "Ryzen 7 PRO 5850U"],
    "elitebook 845 g8": ["Ryzen 5 PRO 5650U", "Ryzen 7 PRO 5850U"],
    "elitebook 835 g9": ["Ryzen 5 PRO 7530U", "Ryzen 7 PRO 7735U"],
    "elitebook 845 g9": ["Ryzen 5 PRO 7530U", "Ryzen 7 PRO 7735U"],
    "elitebook 835 g10": ["Ryzen 5 PRO 7540U", "Ryzen 7 PRO 7840U"],
    "elitebook 845 g10": ["Ryzen 5 PRO 7540U", "Ryzen 7 PRO 7840U"],
    "elitebook 1040 g7": ["i5-10210U", "i7-10510U", "i7-10710U"],
    "elitebook 1040 g8": ["i5-1145G7", "i7-1165G7", "i7-1185G7"],
    "elitebook 1040 g9": ["i5-1240P", "i7-1260P", "i7-1280P"],
    "elitebook 1040 g10": ["i5-1355U", "i7-1365U", "i7-1370P"],
    "elitebook 640 g8": ["i5-1135G7", "i7-1165G7"],
    "elitebook 640 g9": ["i5-1235U", "i7-1255U"],
    "probook 430 g7": ["i5-10210U", "i7-10510U"],
    "probook 440 g7": ["i5-10210U", "i7-10510U"],
    "probook 450 g7": ["i5-10210U", "i7-10510U"],
    "probook 430 g8": ["i5-1135G7", "i7-1165G7"],
    "probook 440 g8": ["i5-1135G7", "i7-1165G7"],
    "probook 450 g8": ["i5-1135G7", "i7-1165G7"],
    "probook 430 g9": ["i5-1235U", "i7-1255U"],
    "probook 440 g9": ["i5-1235U", "i7-1255U"],
    "probook 450 g9": ["i5-1235U", "i7-1255U"],
    "probook 430 g10": ["i5-1335U", "i7-1355U"],
    "probook 440 g10": ["i5-1335U", "i7-1355U"],
    "probook 450 g10": ["i5-1335U", "i7-1355U"],
    "probook 635 aero g7": ["Ryzen 5 5600U", "Ryzen 5 PRO 5650U"],
    "probook 635 aero g8": ["Ryzen 5 7530U", "Ryzen 7 7730U"],
    "zbook firefly 14 g7": ["i5-10210U", "i7-10510U", "i7-10710U"],
    "zbook firefly 14 g8": ["i5-1135G7", "i7-1165G7", "i7-1185G7"],
    "zbook firefly 14 g9": ["i5-1235U", "i7-1255U", "i7-1260P"],
    "zbook firefly 14 g10": ["i5-1355U", "i7-1365U"],
    "zbook firefly 14 g11": ["Core Ultra 5 125U", "Core Ultra 7 155U", "Core Ultra 7 165U"],
    "zbook studio g7": ["i7-10750H", "i7-10850H", "Xeon W-10855M"],
    "zbook studio g8": ["i7-11800H", "i9-11950H", "Xeon W-11855M"],
    "zbook studio g9": ["i7-12700H", "i7-12800H"],
    # Apple MacBook by year (unambiguous years only)
    "macbook air 2020": ["M1"],
    "macbook air 2022": ["M2"],
    "macbook air 2023": ["M2"],
    "macbook air 2024": ["M3"],
    "macbook air 2025": ["M4"],
    "macbook pro 13 2020": ["M1"],
    "macbook pro 14 2021": ["M1 Pro", "M1 Max"],
    "macbook pro 16 2021": ["M1 Pro", "M1 Max"],
    "macbook pro 14 2023": ["M2 Pro", "M2 Max", "M3 Pro", "M3 Max"],
    "macbook pro 16 2023": ["M2 Pro", "M2 Max", "M3 Pro", "M3 Max"],
    "macbook pro 14 2024": ["M4", "M4 Pro", "M4 Max"],
    "macbook pro 16 2024": ["M4 Pro", "M4 Max"],
    # mini desktops (office micros)
    "thinkcentre m75q gen 2": ["Ryzen 3 PRO 4350GE", "Ryzen 5 PRO 4650GE", "Ryzen 7 PRO 4750GE", "Ryzen 5 PRO 5650GE"],
    "thinkcentre m90q": ["i5-10400T", "i5-10500T", "i7-10700T"],
    "thinkcentre m70q gen 3": ["i5-12400T", "i7-12700T"],
    "elitedesk 800 g6 mini": ["i5-10400", "i5-10500", "i7-10700"],
    "elitedesk 800 g8 mini": ["i5-11400", "i5-11500", "i7-11700"],
    "elitedesk 800 g9 mini": ["i5-12400", "i5-12500", "i7-12700"],
    "prodesk 600 g9 mini": ["i5-12400", "i5-12500"],
    "optiplex 3090 micro": ["i3-10105T", "i5-10500T"],
    "optiplex 5090 micro": ["i5-10500T", "i7-10700T"],
    "optiplex 7090 micro": ["i5-10500", "i7-10700"],
    "optiplex 3000 micro": ["i3-12100T", "i5-12400T"],
    "optiplex 5000 micro": ["i5-12400T", "i7-12700T"],
    "optiplex 7000 micro": ["i5-12400", "i7-12700"],
})


# board model -> soldered CPU options. Consulted ONLY when the text names a
# board (board/mainboard/logicboard/motherboard/platine/...), so whole-laptop
# listings keep their (usually identical) MODEL_CPU_SEED path. Common factory
# configs first; drawer offers the rest. No bench source for ARM SBC chips
# (BCM/RKxxxx) — those stay honestly unrated, flagged as platforms.
BOARD_CPU_SEED = {
    # ThinkPad AMD boards (beyond MODEL_CPU_SEED's Intel-leaning classics)
    "thinkpad e14 gen 2": ["Ryzen 5 5500U", "Ryzen 7 5700U"],
    "e14 gen 2": ["Ryzen 5 5500U", "Ryzen 7 5700U"],
    "thinkpad e15 gen 2": ["Ryzen 5 5500U", "Ryzen 7 5700U"],
    "e15 gen 2": ["Ryzen 5 5500U", "Ryzen 7 5700U"],
    "thinkpad e15 gen 3": ["Ryzen 5 5500U", "Ryzen 7 5700U", "Ryzen 5 7530U"],
    "thinkpad l14 gen 1": ["Ryzen 5 PRO 4650U", "Ryzen 7 PRO 4750U"],
    "l14 gen 1": ["Ryzen 5 PRO 4650U", "Ryzen 7 PRO 4750U"],
    "thinkpad p14s gen 1": ["Ryzen 7 PRO 4750U"],
    "p14s gen 1": ["Ryzen 7 PRO 4750U"],
    "thinkpad x13 gen 1": ["Ryzen 5 PRO 4650U", "Ryzen 7 PRO 4750U"],
    "x13 gen 1": ["Ryzen 5 PRO 4650U", "Ryzen 7 PRO 4750U"],
    "thinkpad t14 gen 1": ["Ryzen 5 PRO 4650U", "Ryzen 7 PRO 4750U"],
    "t14 gen 1": ["Ryzen 5 PRO 4650U", "Ryzen 7 PRO 4750U"],
    # IdeaPad / Yoga Slim boards
    "ideapad 3": ["Ryzen 5 5500U", "Ryzen 7 5700U", "Ryzen 7 5825U"],
    "ideapad 5": ["Ryzen 7 5700U", "Ryzen 7 5825U", "Ryzen 5 7530U"],
    "ideapad slim 5": ["Ryzen 5 5500U", "Ryzen 7 5700U", "Ryzen 5 7530U"],
    "ideapad slim 7": ["Ryzen 7 5800U", "Ryzen 7 5800HS", "Ryzen 7 7735HS"],
    "yoga slim 7": ["Ryzen 7 5800U", "Ryzen 7 5800HS", "Ryzen 7 6800HS", "Ryzen 7 7735HS"],
    "ideapad gaming 3": ["Ryzen 5 5600H", "Ryzen 7 5800H"],
    # HP boards
    "elitebook 845 g7": ["Ryzen 7 PRO 4750U"],
    "elitebook 845 g8": ["Ryzen 5 PRO 5650U", "Ryzen 7 PRO 5850U"],
    "elitebook 835 g7": ["Ryzen 5 PRO 4650U", "Ryzen 7 PRO 4750U"],
    "elitebook 835 g8": ["Ryzen 5 PRO 5650U", "Ryzen 7 PRO 5850U"],
    "probook 445 g7": ["Ryzen 5 4500U", "Ryzen 7 4700U"],
    "probook 445 g8": ["Ryzen 5 5650U", "Ryzen 7 5850U", "Ryzen 5 PRO 5650U"],
    "probook 455 g8": ["Ryzen 5 5650U", "Ryzen 7 5850U"],
    "probook 455 g9": ["Ryzen 5 7530U", "Ryzen 7 7735U"],
    "pavilion 15": ["Ryzen 5 5500U", "Ryzen 7 5700U"],
    "omen 15": ["Ryzen 5 5600H", "Ryzen 7 5800H"],
    "omen 16": ["Ryzen 7 6800H", "i7-12700H"],
    "hp 14": ["Ryzen 5 5500U", "Ryzen 7 5700U"],
    "hp 15": ["Ryzen 5 5500U", "Ryzen 7 5700U", "Ryzen 5 7530U"],
    "elitedesk 805 g6": ["Ryzen 5 PRO 4650GE", "Ryzen 7 PRO 4750G"],
    "prodesk 405 g6": ["Ryzen 5 PRO 4650GE"],
    # Dell boards
    "latitude 5420": ["i5-1145G7", "i7-1165G7"],
    "latitude 5430": ["i5-1235U", "i5-1245U", "i7-1255U"],
    "latitude 5400": ["i5-8265U", "i7-8665U"],
    "latitude 5410": ["i5-10210U", "i5-10310U", "i7-10510U"],
    "inspiron 5505": ["Ryzen 5 4500U", "Ryzen 7 4700U"],
    "inspiron 5515": ["Ryzen 5 5500U", "Ryzen 7 5700U"],
    "g5 5500": ["i5-10300H", "i7-10750H"],
    "g15 5511": ["i5-11400H", "i7-11800H"],
    "optiplex 3090": ["i3-10105T", "i5-10500T"],
    "optiplex 5090": ["i5-10500T", "i7-10700T"],
    "optiplex 7090": ["i5-10500", "i7-10700"],
    # Apple logic boards
    "macbook air m1": ["M1"],
    "macbook air m2": ["M2"],
    "macbook pro 13 m1": ["M1"],
    "macbook pro 13 m2": ["M2"],
    "macbook pro 14": ["M1 Pro", "M1 Max"],
    "macbook pro 16": ["M1 Pro", "M1 Max", "M2 Pro", "M2 Max"],
    "mac mini m1": ["M1"],
    "mac mini m2": ["M2"],
    "imac 24": ["M1"],
    # Framework mainboards (premium, swappable)
    "framework 13": ["i5-1240P", "i7-1360P", "Ryzen 5 7640U", "Ryzen 7 7840U"],
    "framework laptop 13": ["i5-1240P", "i7-1360P", "Ryzen 5 7640U", "Ryzen 7 7840U"],
    "framework 16": ["Ryzen 7 7840HS", "Ryzen 9 7940HS"],
    "framework laptop 16": ["Ryzen 7 7840HS", "Ryzen 9 7940HS"],
    # Mini-PC boards
    "morefine m600": ["Ryzen 5 6600H", "Ryzen 7 6800H"],
    "minisforum um690": ["Ryzen 9 6900HX"],
    "beelink ser5": ["Ryzen 5 5600H", "Ryzen 7 5800H"],
    # Server boards shipped with CPU (AI-rig relevant)
    "h11dsi": ["EPYC 7302", "EPYC 7402", "EPYC 7502"],
    "h12dsi": ["EPYC 7532", "EPYC 7542"],
    "x11dpi": ["Xeon Gold 6130", "Xeon Gold 6148"],
    "x10drl": ["Xeon E5-2620V4", "Xeon E5-2667V4"],
    # ARM SBCs (no PassMark source — recognized as platforms, honestly unrated)
    "raspberry pi 5": ["BCM2712"],
    "raspberry pi 4": ["BCM2711"],
    "orange pi 5": ["RK3588S"],
    "rock 5": ["RK3588"],
    # ThinkPad S-slims + X380 (frequent board listings)
    "t460s": ["i5-6200U", "i5-6300U", "i7-6500U", "i7-6600U"],
    "thinkpad t460s": ["i5-6200U", "i5-6300U", "i7-6500U", "i7-6600U"],
    "t470s": ["i5-7200U", "i5-7300U", "i7-7500U", "i7-7600U"],
    "thinkpad t470s": ["i5-7200U", "i5-7300U", "i7-7500U", "i7-7600U"],
    "t480s": ["i5-8250U", "i5-8350U", "i7-8550U", "i7-8650U"],
    "thinkpad t480s": ["i5-8250U", "i5-8350U", "i7-8550U", "i7-8650U"],
    "t490s": ["i5-8265U", "i5-8365U", "i7-8565U", "i7-8665U"],
    "x380 yoga": ["i5-8250U", "i5-8350U", "i7-8550U", "i7-8650U"],
    "thinkpad x380 yoga": ["i5-8250U", "i5-8350U", "i7-8550U", "i7-8650U"],
    # Apple A-model boards (Axxxx = exact machine, disambiguates Intel-vs-Apple Silicon years)
    "a1181": ["T7500"],
    "a1278": ["i5-2415M", "i5-3210M"],
    "a1342": ["P8600"],
    "a1369": ["i5-2537M"],
    "a1370": ["i5-2467M"],
    "a1398": ["i7-4770HQ", "i7-4980HQ"],
    "a1425": ["i5-5257U", "i7-5557U"],
    "a1466": ["i5-5250U", "i7-5650U"],
    "a1502": ["i5-4278U", "i7-5557U"],
    "a1534": ["M-5Y51", "M-5Y71"],
    "a1706": ["i5-6267U", "i7-6667U"],
    "a1707": ["i7-6700HQ", "i7-6820HQ", "i7-6920HQ"],
    "a1708": ["i5-6360U"],
    "a1932": ["i5-8210Y"],
    "a1989": ["i5-8259U", "i7-8559U"],
    "a1990": ["i7-8750H", "i7-8850H", "i9-8950HK"],
    "a2141": ["i7-9750H", "i9-9880H", "i9-9980HK"],
    "a2159": ["i5-8257U"],
    "a2179": ["i5-1038NG7"],
    "a2251": ["i5-1038NG7", "i7-1068NG7"],
    "a2289": ["i5-1038NG7"],
    "a2338": ["M1"],
    "a2442": ["M1"],
    "a2485": ["M1 Pro"],
    "a2681": ["M2"],
    "a2779": ["M2"],
}

BOARD_WORDS = re.compile(
    r"mainboard|motherboard|logic\s*board|logicboard|baseboard|systemboard|"
    r"hauptplatine|systemplatine|\bplatine\b", re.IGNORECASE)

#: Spare-part nouns: the listing SELLS the part, not a system containing it.
#: "Display Assembly" / palmrest / case shells must never inherit a CPU bench,
#: while "Display defekt" (broken screen on a whole machine) flows normally.
PART_NOUNS = re.compile(
    r"display\s*assembly|ersatzdisplay|displayeinheit|palmrest|unterschale|"
    r"oberschale|topcase|bottomcase|displaydeckel|tastaturabdeckung", re.IGNORECASE)
#: Compounds only: a bare "usb" (USB-C port mention) must never nuke a real board.
IO_BOARD_WORDS = re.compile(
    r"i/o\b|io[-\s]?(board|platine|karte)|usb[-\s]?(board|platine)|"
    r"lan[-\s]?(board|platine)|audio[-\s]?(board|platine)|hdmi[-\s]?(board|platine)|"
    r"power[-\s]?(board|button)|led[-\s]?board|sub[-\s]?board|daughter\s?board|"
    r"tastatur[-\s]?platine|keyboard[-\s]?board|lese[-\s]?platine", re.IGNORECASE)

SOCKET_WORDS = re.compile(
    r"\bam4\b|\bam5\b|lga\s*1700|lga\s*1200|lga\s*1151|\btr4\b|\bsp3\b|"
    r"x670e?|b650e?|x570|b550|a520|z790|b760|z690|b660|x399|wrX80|wrx90", re.IGNORECASE)


def _seed_hit(seed_key: str, bl: str, bl_nospace: str) -> bool:
    """Short keys (x270, t460, a2141) must match as whole tokens AND with brand
    context — otherwise dimensions ("172 x270 cm") conjure phantom CPUs."""
    nospace = re.sub(r"[^a-z0-9]", "", seed_key)
    if len(nospace) <= 8:
        if not re.search(r"(?<![a-z0-9])" + re.escape(seed_key) + r"(?![a-z0-9])", bl):
            return False
        return bool(re.search(
            r"thinkpad|lenovo|latitude|elitebook|probook|zbook|ideapad|yoga|legion|"
            r"\bhp\b|dell|apple|macbook|\bmac\b|framework|pavilion|omen|victus|inspiron|"
            r"board|mainboard|motherboard|logic|platine", bl))
    return seed_key in bl or nospace in bl_nospace


async def resolve_cpu_candidates(model_name: str) -> list[str]:
    """Which CPUs ship in this laptop model? Seed table + AI, disk-cached."""
    import json as _json
    key = model_name.strip().lower()
    if not key:
        return []
    if key in MODEL_CPU_SEED:
        return MODEL_CPU_SEED[key]
    try:
        from pathlib import Path as _P
        p = _P("data/cpu_models.json")
        cache = _json.loads(p.read_text()) if p.exists() else {}
        if key in cache:
            return cache[key]
    except Exception:
        cache = {}
    from .decision import cloud_json
    out = await cloud_json(
        "You know laptop hardware lineups. Return ONLY JSON {cpus: [exact CPU model names]}.",
        f"Which CPU options exist for the laptop model '{model_name}'? List 1-6 exact names.")
    cpus = [str(c) for c in (out.get("cpus", []) if out else [])][:6]
    if cpus:
        try:
            cache[key] = cpus
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(_json.dumps(cache))
        except Exception:
            pass
    return cpus


def strip_marketplace_suffix(text: str) -> str:
    """Cut marketplace-appended metadata tails (vinted: ", Marke: X, Modell: Y,
    Zustand: Z, ...") that dilute spec extraction. The Modell: value is kept
    (it often names the exact machine, e.g. "ThinkPad X250") and appended to
    the head; the rest of the metadata is dropped."""
    import re as _re0
    src = text or ""
    keep = ""
    m_mod = _re0.search(r"modell\s*:\s*([^,]{2,80})", src, _re0.IGNORECASE)
    if m_mod:
        keep = " " + m_mod.group(1).strip()
    m = _re0.search(r",\s*marke\s*:", src, _re0.IGNORECASE)
    head = src[:m.start()] if m else src
    return (head.strip() + keep).strip()


def extract_cpu(text: str) -> tuple[str | None, float, str]:
    t = strip_marketplace_suffix(text).lower()

    def _apple_chip_ok(pos: int, length: int) -> bool:
        """Apple Silicon needs word boundaries AND context: AM18/M100/M330C/BMW M1
        are model numbers and cars, not M-chips. '256 M2' is an SSD size."""
        if re.search(r"\d+\s*$", t[max(0, pos - 8):pos]):
            return False  # storage size directly before: "256 M2", "512 M1" SSD
        before = t[max(0, pos - 12):pos]
        after = t[pos + length:pos + length + 12]
        return bool(re.search(r"(apple|macbook|imac|mac\s*mini|mac\s*studio|ipad"
                              r"|chip|soc|\d+\s*gb|ram|ssd|speicher)", before + " " + after))

    for cpu in CPU_DB:
        if cpu in t:
            if re.match(r"m[1-4]$", cpu):
                m0 = re.search(r"(?<![a-z0-9])" + re.escape(cpu) + r"(?![a-z0-9])", t)
                if not m0:
                    continue
                if not _apple_chip_ok(m0.start(), len(cpu)):
                    continue
                i = m0.start()
                ctx = t[max(0, i - 10):i + len(cpu) + 10]
                if re.search(r"m\s*\.\s*[1-4]|ssd|nvme|\bslot\b|2280|2230|2242", ctx):
                    continue  # M.2 SSD storage next to the match, not Apple Silicon
            return cpu, 0.9, f"mentioned '{cpu}'"
    # Intel Core Ultra: "Ultra 5 235H", "Core Ultra 7 155H", "Ultra 9 285HX"
    m = re.search(r"(?:core\s+)?ultra\s*([579])\s*(\d{3,4}\s*[a-z]*)", t)
    if m:
        num = re.sub(r"\s+", "", m.group(2)).upper()
        g = f"Core Ultra {m.group(1)} {num}"
        return g, 0.8, f"mentioned '{g}'"
    # Intel Core Ultra X (Panther Lake+): "Ultra X7 358H", "Core Ultra X9".
    # Bare series ("Ultra X7", no number) stays an honest low-confidence label;
    # benchmark lookup skips it (no digits) until the drawer sets the exact SKU.
    m = re.search(r"(?:core\s+)?ultra\s*x\s*([579])(?:\s*(\d{3,4}\s*[a-z]*))?\b", t)
    if m:
        if m.group(2):
            num = re.sub(r"\s+", "", m.group(2)).upper()
            g = f"Core Ultra X{m.group(1)} {num}"
            return g, 0.8, f"mentioned '{g}'"
        g = f"Core Ultra X{m.group(1)}"
        return g, 0.55, f"mentioned '{g}' (series only, exact SKU unknown)"
    # Nth-gen shorthand: "i3 10th", "i5 11th" -> most common U SKU of that gen.
    m = re.search(r"\bi([357])\s*(\d{1,2})(?:st|nd|rd|th)\b", t)
    if m:
        _nth = {"8": {"3": "i3-8130U", "5": "i5-8250U", "7": "i7-8550U"},
                "10": {"3": "i3-10110U", "5": "i5-10210U", "7": "i7-10510U"},
                "11": {"3": "i3-1115G4", "5": "i5-1135G7", "7": "i7-1165G7"},
                "12": {"3": "i3-1215U", "5": "i5-1235U", "7": "i7-1255U"},
                "13": {"3": "i3-1315U", "5": "i5-1335U", "7": "i7-1355U"}}.get(m.group(2), {}).get(m.group(1))
        if _nth:
            return _nth, 0.5, f"shorthand 'i{m.group(1)} {m.group(2)}th' -> {_nth}"
    # Ryzen AI: "Ryzen AI 9 HX 370", "Ryzen AI 7 PRO 350", "Ryzen AI 5 340"
    m = re.search(r"ryzen\s+ai\s+(\d+)\s*(pro\s+)?(hx\s+)?(\d{3})\b", t)
    if m:
        parts = ["Ryzen", "AI", m.group(1)]
        if m.group(2):
            parts.append("PRO")
        if m.group(3):
            parts.append("HX")
        parts.append(m.group(4))
        g = " ".join(parts)
        return g, 0.8, f"mentioned '{g}'"
    # space-form Intel: "i7 12700H", "i5 12450H", "i7 8650-U", "i5 1145G7".
    # Suffix needs a non-letter after it ("i5 2500 Prozessor" is NOT i5-2500PRO).
    m = re.search(r"\bi\s*([3579])\s+(\d{4,5})\s*-?\s*([a-z]{1,2}\d?)?(?![a-z])", t)
    if m:
        suf = (m.group(3) or "").upper()
        g = f"i{m.group(1)}-{m.group(2)}{suf}"
        return g, 0.7, f"mentioned '{g}'"
    # Xeon: "Xeon E-2276M", "Xeon W-10855M", "Xeon E3-1505M"
    m = re.search(r"\bxeon\s*(e[35]?-|w-)?\s*(\d{4,5}[a-z]*)\b", t)
    if m:
        g = f"Xeon {(m.group(1) or '').upper()}{m.group(2).upper()}"
        return g.strip(), 0.8, f"mentioned '{g.strip()}'"
    # EPYC: "EPYC 7351P", "EPYC 7302", "EPYC 7542" (server/AI-rig relevant)
    m = re.search(r"\bepyc\s*(\d{3,4}[a-z]*)\b", t)
    if m:
        g = f"EPYC {m.group(1).upper()}"
        return g, 0.8, f"mentioned '{g}'"
    # bare Intel mobile/desktop: "8650U", "1145G7", "12450H", "12700".
    # 6/7/8xxx+U/H collides with AMD numbering -> decide by nearby brand context,
    # else skip (model-seed family estimate covers business lines honestly).
    m = re.search(r"\b(\d{4})\s*-?\s*(u|h)\b|\b(\d{5})\s*([a-z]{1,3})\b", t)
    if m:
        if m.group(1):
            num, suf = m.group(1), m.group(2)
            # explicit tier glued on ("i7-1255U"): trust it, never re-derive
            pre = re.search(r"i([3579])\s*-$", t[max(0, m.start() - 4):m.start()])
            if pre:
                return f"i{pre.group(1)}-{num}{suf.upper()}", 0.75, \
                    f"explicit 'i{pre.group(1)}-{num}{suf.upper()}'"
            ctx = t[max(0, m.start() - 24):m.end() + 8]
            intel_ctx = bool(re.search(r"intel|\bi[3579]\b|nuc|optiplex|elitedesk|prodesk|vostro|surface|celeron|pentium", ctx))
            mixed_ctx = bool(re.search(r"thinkpad|latitude|elitebook|probook|zbook|thinkcentre", ctx))
            amd_ctx = bool(re.search(r"ryzen|amd|\br[3579]\b|radeon", ctx))
            if num[0] in "678" and not intel_ctx and not amd_ctx:
                pass  # ambiguous: let model-seed estimate handle it
            elif intel_ctx or (num[0] in "678" and not amd_ctx and not mixed_ctx):
                tier = {"2": "5", "3": "5", "5": "7", "6": "7"}.get(num[1], "")
                if tier:
                    return f"i{tier}-{num}{suf.upper()}", 0.6, f"bare '{num}{suf}' (intel context) -> i{tier}"
            # AMD 4-digit mobile lives in the shared bare-AMD branch below
        else:
            num, suf = m.group(3), m.group(4)
            if num == "1195G7":
                return "i7-1195G7", 0.7, "known i7 exception"
            tier = {"0": "3", "1": "3", "2": "5", "3": "5", "4": "5",
                    "5": "7", "6": "7", "7": "7", "8": "7", "9": "9"}.get(num[2], "")
            if tier and suf in ("u", "h", "hx", "p", "g", "g7", "t", "f", "k", "kf", "hk"):
                return f"i{tier}-{num}{suf.upper()}", 0.6, f"bare '{num}{suf}' -> i{tier}"
    # explicit Ryzen with number: "Ryzen 5 PRO 5650U", "Ryzen 7 8845HS",
    # "Ryzen 3 4300U", "Ryzen 5 5600G", "Ryzen 9 9950X3D" (normalized).
    # Sellers split the letter: "Ryzen 7 H 255", "Ryzen 7 H255" (= Ryzen 7 255).
    # Adjacent tier+model ("Ryzen 5800H") keeps the tier digit in the model
    # ("5800H", NOT "800H"); spaced ("Ryzen 7 255") takes the rest as-is.
    m = re.search(r"ryzen\s*([3579])(?:\s+(pro))?\s*(h\s*)?(\d{3,4}[a-z0-9]*)", t)
    if m:
        tier, pro, hsplit, rest = m.group(1), m.group(2), m.group(3), \
            re.sub(r"\s+", "", m.group(4)).upper()
        adjacent = bool(re.match(r"ryzen\s*[3579]\d", t[m.start():m.start() + 12]))
        digits = re.match(r"\d+", rest)
        if adjacent and not pro and not hsplit and digits and len(digits.group(0)) == 3:
            rest = tier + rest
        g = f"Ryzen {tier} " + ("PRO " if pro else "") + rest
        ev = f"mentioned '{g}'"
        if hsplit:
            ev += " (seller split 'H' prefix)"
        return g, 0.85, ev
    # bare AMD numbers: "8845HS", "R7 7840U", "7735 HS", "5600G" -> tier from 2nd
    # digit (2/3/4->Ryzen 3, 5/6->Ryzen 5, 7/8->Ryzen 7, 9->Ryzen 9).
    # Skipped when an explicit "Ryzen <tier>" prefix exists (handled above).
    if not re.search(r"ryzen\s*[3579]", t):
        m = re.search(r"\br\s*([3579])\s*(\d{4})\s*([a-z]{1,2})\b"
                      r"|\b(\d{4})\s*(hs|hx|h|u|g|ge|x3d|x|f)\b", t)
        if m:
            # RAM-speed markings are not CPUs ("PC2-5300U", "667 MHz DIMM").
            # Screen resolutions are not CPUs ("2560 x 1600", "1920x1080").
            # Intel context is not an AMD CPU ("INTEL i7-8750H" is not Ryzen 7).
            _ctx = t[max(0, m.start() - 10):m.end() + 10]
            _is_ram = bool(re.search(r"pc\d*-\d+|\d+\s*mhz|\bdimm\b|\bsodimm\b", _ctx, re.IGNORECASE))
            _is_res = bool(re.search(r"\d{3,4}\s*x\s*\d{3,4}", _ctx))
            _is_intel = bool(re.search(r"\bintel\b|\bi[3579]\b", _ctx))
            tier, num, suf = "", "", ""
            if not _is_ram and not _is_intel and not _is_res:
                if m.group(1):
                    tier, num, suf = m.group(1), m.group(2), m.group(3)
                else:
                    num, suf = m.group(4), m.group(5)
                    # desktop X/X3D/F/G parts: tier by first two digits
                    tier = {"12": "3", "13": "3", "14": "3", "15": "3", "16": "5",
                            "17": "7", "18": "7", "22": "3", "23": "3", "24": "3",
                            "26": "5", "27": "7", "32": "3", "33": "3", "34": "3",
                            "35": "3", "36": "5", "37": "7", "38": "7", "39": "9",
                            "43": "3", "44": "3", "45": "5", "46": "3", "47": "7",
                            "48": "7", "49": "7", "53": "3", "54": "3", "55": "5",
                            "56": "5", "57": "7", "58": "7", "59": "9", "76": "5",
                            "77": "7", "78": "7", "79": "9", "95": "9", "99": "9"}.get(num[:2], "")
                    if not tier:
                        tier = {"2": "3", "3": "3", "4": "3", "5": "5", "6": "5",
                                "7": "7", "8": "7", "9": "9"}.get(num[1], "")
            if tier and suf in ("h", "hs", "hx", "u", "g", "ge", "x3d", "x", "f"):
                g = f"Ryzen {tier} {num}{suf.upper()}"
                return g, 0.7, f"bare model '{num}{suf}' -> {g}"
    for m in re.finditer(r"(ryzen\s*\d+\s*\w*|i[3579]-\d{4,5}\w*|(?<![a-z0-9])m[1-4](\s*(pro|max))?(?![a-z0-9]))", t):
        g = (m.group(1) or "").strip()
        if re.match(r"i[3579]-", g, re.IGNORECASE):
            g = g[0].lower() + g[1:].upper()  # i5-12450h -> i5-12450H
        # M.2 SSD slots are storage, not Apple Silicon — skip those matches
        ctx = t[max(0, m.start() - 8):m.end() + 8]
        if re.match(r"m[1-4]", g, re.IGNORECASE):
            if re.search(r"m\s*\.\s*2|ssd|nvme|slot|2280|2230", ctx, re.IGNORECASE):
                continue
            if not _apple_chip_ok(m.start(), len(g)):
                continue  # BMW M1 and friends are not Apple Silicon
        # RAM-speed markings are not CPUs ("PC2-5300U", "667 MHz DIMM")
        # ...unless a real Ryzen tier prefix leads ("Ryzen 5 5600U ... DDR4")
        if re.search(r"pc\d*-\d+|\d+\s*mhz|\bdimm\b|\bsodimm\b", ctx, re.IGNORECASE) \
                and not re.search(r"ryzen\s*[3579]", t[max(0, m.start() - 24):m.start()]):
            continue
        return g, 0.45, f"pattern '{g}' (unverified)"
    return None, 0.0, ""


def resolve_cpu_with_seeds(text: str) -> tuple[str | None, float, str, bool, list[str]]:
    """Exact mention first, else model-family seed estimate (sync, no AI).

    Returns (cpu, conf, why, estimated, candidates). Bare tier hints narrow the
    seed ("X1 Carbon Gen 6" + "i5" -> i5-8350U first, not the i7 base).
    """
    clean = strip_marketplace_suffix(text)
    # Spare parts are never systems: a display assembly carries no bench even
    # when it names the machine it fits.
    if PART_NOUNS.search(clean):
        return None, 0.0, "", False, []
    cpu, conf, why = extract_cpu(clean)
    # Solid mentions win immediately; vague unverified fragments ("ryzen 5",
    # "ryzen 7") defer to the seed tables below, which attach candidates.
    if cpu and (conf >= 0.6 or "unverified" not in why):
        return cpu, conf, why, False, []
    # IO daughterboards (USB/LAN/power) carry no CPU — never estimate one.
    if IO_BOARD_WORDS.search(clean):
        return None, 0.0, "", False, []
    bl = clean.lower()
    # normalize generation spellings so seeds match: "5th Gen" -> "gen 5",
    # "X1 Carbon G11" -> "x1 carbon gen 11", "X1 Yoga G8" likewise.
    bl = re.sub(r"(\d+)(?:st|nd|rd|th)\s*gen\b", r"gen \1", bl)
    bl = re.sub(r"\bx1\s+(carbon|yoga|extreme)\s+g(\d+)\b", r"x1 \1 gen \2", bl)
    bl_nospace = re.sub(r"[^a-z0-9]", "", bl)
    # bare tier hint: "i5", "i7", "ryzen 5/7", "ultra 5/7"
    tier_m = re.search(r"\bryzen\s*([3579])\b|\bultra\s*([579])\b|\bi([3579])\b", bl)
    tier = tier_m.group(1) or tier_m.group(2) or tier_m.group(3) if tier_m else None
    # longest seed key first so "thinkpad x1 carbon gen 6" beats "x1 carbon"
    for seed_key in sorted(MODEL_CPU_SEED, key=len, reverse=True):
        if _seed_hit(seed_key, bl, bl_nospace):
            cands = MODEL_CPU_SEED[seed_key]
            if any(c.lower() in bl for c in cands):
                continue  # exact candidate present; extract should have caught it
            narrowed = cands
            if tier:
                hit = [c for c in cands
                       if re.search(rf"(?:^|[\s-])i{tier}-", c.lower())
                       or re.search(rf"ryzen\s*{tier}\b", c.lower())
                       or re.search(rf"ultra\s*{tier}\b", c.lower())]
                if hit:
                    narrowed = hit
            base = narrowed[0]
            others = ", ".join(narrowed[1:4])
            detail = (f"family estimate for '{seed_key}' (could be {base}"
                      f"{', ' + others if others else ''} — set exact CPU in drawer)")
            return base, 0.45, detail, True, cands[:6]
    # board fallback: board model named but no CPU in text ("X13 Gen1 board").
    # Requires a soldered-system board word (IO daughterboards and bare socket
    # platforms excluded); whole machines never land here. Exact Apple A-model
    # IDs (A2141 = 2019 Intel) win over generic line names.
    _is_b, _sock = board_info(clean)
    if _is_b and not _sock:
        import re as _reB
        keys = sorted(BOARD_CPU_SEED, key=len, reverse=True)
        keys.sort(key=lambda k: 0 if _reB.fullmatch(r"a\d{4}", k) else 1)

        def _board_hit(seed_key: str) -> tuple[str | None, float, str, bool, list[str]] | None:
            if _seed_hit(seed_key, bl, bl_nospace):
                cands = BOARD_CPU_SEED[seed_key]
                if any(c.lower() in bl for c in cands):
                    return None
                base = cands[0]
                others = ", ".join(cands[1:4])
                return base, 0.4, (f"board estimate for '{seed_key}' (could be {base}"
                                   f"{', ' + others if others else ''} — set exact CPU in drawer)"), True, cands[:6]
            return None

        for seed_key in keys:
            _bhit = _board_hit(seed_key)
            if _bhit:
                return _bhit
    if cpu:
        return cpu, conf, why, False, []
    return None, 0.0, "", False, []


GPU_PATS = [
    r"rtx\s*\d{3,4}(?:\s*ti)?(?:\s*super)?(?:\s*laptop)?",
    r"rx\s*\d{3,4}(?:\s*m|\s*xt)?",
    r"gtx\s*\d{3,4}(?:\s*ti)?(?:\s*super)?",
    r"rtx\s*a\d{3,4}",
    r"quadro\s*\w+\d+",
    r"arc\s*a\d{3}",
    r"arc\s*1[34]0[vt]",  # Lunar/Arrow Lake iGPU: Arc 130V/140V/140T
    r"radeon\s*[678]8\d\s*m",  # RDNA iGPU: 780M/880M/890M
    r"\b[678]80m\b",  # bare iGPU mention: "780M graphics"
    r"rx\s*vega\s*\d+",
    r"\bvega\s*(?:graphics\s*)?\d+\b",  # bare "Vega 7", "Vega8 Graphics"
]


_IGPU_FULL = re.compile(r"arc\s*1[34]0[vt]|radeon\s*[678]8\d\s*m|\b[678]80m\b|rx\s*vega\s*\d+|"
                        r"\bvega\s*(?:graphics\s*)?\d+", re.IGNORECASE)


# vendor-published specs (stable): VRAM GB + memory bandwidth GB/s.
# est_tps_13b = bw / 7 ≈ tokens/s ceiling for a 13B-active Q4 MoE (DeepSeek-class);
# real-world lands at 40-70% of ceiling (framework overhead, batch=1).
GPU_SPECS = {
    "5090": {"vram": 32, "bw": 1792}, "5080": {"vram": 16, "bw": 960},
    "4090": {"vram": 24, "bw": 1008}, "4080": {"vram": 16, "bw": 717},
    "3090": {"vram": 24, "bw": 936}, "3080": {"vram": 12, "bw": 912},
    "4070": {"vram": 12, "bw": 504}, "7900xtx": {"vram": 24, "bw": 960},
    "9070xt": {"vram": 16, "bw": 640}, "7900xt": {"vram": 20, "bw": 800},
    "p40": {"vram": 24, "bw": 346}, "p100": {"vram": 16, "bw": 732},
    "v100": {"vram": 16, "bw": 900}, "a100": {"vram": 80, "bw": 2039},
    "h100": {"vram": 80, "bw": 3350}, "a6000": {"vram": 48, "bw": 768},
    "6000ada": {"vram": 48, "bw": 960}, "titanrtx": {"vram": 24, "bw": 672},
    "2080ti": {"vram": 11, "bw": 616}, "1080ti": {"vram": 11, "bw": 484},
    "m1max": {"vram": 64, "bw": 400}, "m1ultra": {"vram": 128, "bw": 800},
    "m2max": {"vram": 96, "bw": 400}, "m2ultra": {"vram": 192, "bw": 800},
    "m3max": {"vram": 128, "bw": 400}, "m3ultra": {"vram": 512, "bw": 800},
    "m4max": {"vram": 128, "bw": 546}, "gb10": {"vram": 128, "bw": 273},
    "dgxspark": {"vram": 128, "bw": 273}, "aimax": {"vram": 128, "bw": 256},
    "strixhalo": {"vram": 128, "bw": 256},
}


def lookup_gpu_spec(name: str) -> dict | None:
    """Static VRAM/bandwidth by normalized GPU name (no network)."""
    n = re.sub(r"[^a-z0-9]+", "", (name or "").lower())
    for key in sorted(GPU_SPECS, key=len, reverse=True):
        if key and key in n:
            return dict(GPU_SPECS[key])
    return None


def extract_gpu(text: str) -> tuple[str | None, float, str]:
    t = text.lower()
    for pat in GPU_PATS:
        m = re.search(pat, t)
        if m:
            g = re.sub(r"\s+", " ", m.group(0)).strip()
            full = len(re.findall(r"\d", g)) >= 3 or bool(_IGPU_FULL.search(g))
            return g, (0.8 if full else 0.45), f"mentioned '{g}'"
    return None, 0.0, ""


def enrich_gpu(listing: CanonicalListing) -> list[EnrichmentFact]:
    blob = f"{listing.title}\n{listing.description}\n{' '.join(listing.ocr_texts)}"
    gpu, conf, ev = extract_gpu(blob)
    if not gpu or conf < 0.7:
        uni = extract_unified_mem(blob)
        if uni:
            return [EnrichmentFact(field="gpu_mem_total", value=uni, confidence=0.7,
                                   status=FactStatus.AI_INFERRED,
                                   sources=[Evidence(type="description",
                                                     detail=f"unified memory {uni}GB (no discrete GPU)",
                                                     confidence=0.7)])]
        return []
    facts = [EnrichmentFact(field="gpu", value=gpu, confidence=conf,
                            status=FactStatus.AI_INFERRED if conf < 0.85 else FactStatus.SUPPORTED,
                            sources=[Evidence(type="description", detail=ev, confidence=conf)])]
    mcount = re.search(r"(\d+)\s*[x×]\s*(?:rtx|gtx|rx|arc|tesla|quadro|radeon|titan|geforce)", blob.lower())
    count = max(1, min(8, int(mcount.group(1)))) if mcount else 1
    if count > 1:
        facts.append(EnrichmentFact(field="gpu_count", value=count, confidence=0.8,
                                    status=FactStatus.AI_INFERRED,
                                    sources=[Evidence(type="description",
                                                      detail=f"{count}x multi-GPU", confidence=0.8)]))
    spec = lookup_gpu_spec(gpu)
    if spec:
        facts.append(EnrichmentFact(field="gpu_vram", value=spec["vram"] * count, confidence=0.9,
                                    status=FactStatus.EXTERNAL,
                                    sources=[Evidence(type="external", detail="vendor spec", confidence=0.9)]))
        facts.append(EnrichmentFact(field="gpu_bw", value=spec["bw"], confidence=0.9,
                                    status=FactStatus.EXTERNAL,
                                    sources=[Evidence(type="external",
                                                      detail="vendor GB/s (single-GPU rate; multi-GPU without NVLink stays ~single)",
                                                      confidence=0.9)]))
        facts.append(EnrichmentFact(field="gpu_est_tps", value=round(spec["bw"] / 7),
                                    confidence=0.5, status=FactStatus.AI_INFERRED,
                                    sources=[Evidence(type="description",
                                                      detail="rough tok/s ceiling for 13B-active Q4 MoE (real: 40-70%)",
                                                      confidence=0.5)]))
    return facts


def extract_unified_mem(text: str) -> int | None:
    """Unified-memory total GB for Apple Silicon / Strix Halo / DGX Spark (no dGPU)."""
    t = text.lower()
    m = re.search(r"(m[1-4]\s*(?:ultra|max|pro)|ryzen ai max|strix halo|gb10|dgx spark|apple\s*m\d)[^.:\n]{0,50}?(\d{2,3})\s*gb", t)
    if m:
        return int(m.group(2))
    m = re.search(r"(\d{2,3})\s*gb\s*(unified|gemeinsamer|shared)\s*(memory|speicher|ram)?", t)
    if m and int(m.group(1)) >= 32:
        return int(m.group(1))
    return None


_UPTO = re.compile(r"(up\s*to|bis\s*zu|\bmax\.?|supports?|erweiterbar|aufrüstbar)\s*$", re.IGNORECASE)


def _upto_guard(t: str, pos: int) -> bool:
    """True when the match at pos is an option maximum ("up to 128GB"), not
    included hardware."""
    return bool(_UPTO.search(t[max(0, pos - 12):pos]))


def extract_ram(text: str) -> int | None:
    """Installed RAM in GB, or None. Requires a memory keyword nearby so SSD
    sizes and model numbers never leak in ("512GB SSD", "M2", "2280").
    Option maximums ("up to 128GB") are not included RAM."""
    t = (text or "").lower()
    for m in re.finditer(r"(\d{2,3})\s*gb\s*(?:ddr\d?|lpddr\d?|sodimm|dimm|ram|arbeitsspeicher|memory|speicher)", t):
        if not _upto_guard(t, m.start()):
            return int(m.group(1))
    for m in re.finditer(r"(?:ram|memory|arbeitsspeicher)[^.:\n]{0,20}?(\d{2,3})\s*gb", t):
        if not _upto_guard(t, m.start(1)):
            return int(m.group(1))
    return None


def extract_storage(text: str) -> tuple[int | None, str]:
    """(capacity GB, kind SSD|NVMe|HDD|''). TB converts x1024. A match naming a
    drive kind (SSD/NVMe/HDD/...) always wins; bare sizes fall back with a RAM
    guard (bare GB under 256 is usually memory, e.g. "16GB, 1TB")."""
    t = (text or "").lower()
    pats = list(re.finditer(
        r"(\d+(?:[.,]\d+)?)\s*(tb|gb)\s*(nvme|ssd|hdd|festplatte|emmc|ufs|speichermedien)?", t))
    if not pats:
        return None, ""
    kinded = [m for m in pats if m.group(3)]
    bare = [m for m in pats if not m.group(3)]

    def _gb(m) -> int | None:
        try:
            size = float(m.group(1).replace(",", "."))
        except ValueError:
            return None
        gb = int(size * 1024) if m.group(2) == "tb" else int(size)
        return gb if 0 < gb <= 65536 else None

    def _kind(m) -> str:
        kind = (m.group(3) or "").upper()
        if kind == "FESTPLATTE":
            return "HDD"
        return "" if kind == "SPEICHERMEDIEN" else kind

    for m in kinded:
        if _upto_guard(t, m.start()):
            continue
        gb = _gb(m)
        if gb:
            return gb, _kind(m)
    for m in bare:
        if _upto_guard(t, m.start()):
            continue
        gb = _gb(m)
        if gb and (m.group(2) == "tb" or gb >= 256):
            return gb, ""
    return None, ""


_PORT_PATS = (
    ("USB4", r"usb\s*4(\.0)?\b"),
    ("Thunderbolt 5", r"thunderbolt\s*5\b"),
    ("Thunderbolt 4", r"thunderbolt\s*4\b"),
    ("Thunderbolt 3", r"thunderbolt\s*3\b"),
    ("USB-C", r"usb[-\s]?c\b|type[-\s]?c\b"),
    ("OCuLink", r"oculink\b"),
    ("HDMI", r"\bhdmi\b"),
    ("DisplayPort", r"displayport\b|\bdp\s*\d"),
    ("2.5G LAN", r"2\.5g(\s*(lan|ethernet))?\b"),
    ("WiFi 7", r"wi-?fi\s*7\b"),
    ("WiFi 6E", r"wi-?fi\s*6e\b"),
    ("SD reader", r"\bsd(\s*(card|reader|slot))?\b"),
)


def extract_ports(text: str) -> list[str]:
    """Notable connectivity worth comparing (mini-PC buying criteria)."""
    t = (text or "").lower()
    return [label for label, pat in _PORT_PATS if re.search(pat, t)]


def is_barebone(text: str) -> bool:
    """No RAM/SSD included (barebone configurables like "0GB/32GB 0TB/1TB")."""
    t = (text or "").lower()
    return bool(re.search(
        r"barebone|\b0\s*gb\b|\b0\s*tb\b|ohne\s*(ram|ssd|speicher|festplatte)"
        r"|without\s*(ram|ssd|storage)|w/o\s*(ram|ssd)|no\s*(ram|ssd)\b"
        r"|ram\s*/\s*ssd\s*(nicht|exkl)|exkl\.\s*(ram|ssd)", t))


def board_info(text: str) -> tuple[bool, bool]:
    """(is_board, socketed). Socketed = desktop/server platform board needing
    its own CPU (no completion math); soldered = usable system core.
    IO daughterboards (USB/LAN/power) are not system boards."""
    blob = text or ""
    if not BOARD_WORDS.search(blob):
        return False, False
    if IO_BOARD_WORDS.search(blob):
        return False, False
    return True, bool(SOCKET_WORDS.search(blob))


#: Typical extra spend to turn a soldered laptop/mini board into a running
#: system (RAM + SSD + PSU/case/cooling). Labeled estimate, not a quote.
BOARD_COMPLETION_EUR = 120


def enrich_specs(listing: CanonicalListing) -> list[EnrichmentFact]:
    """Cheap regex-tier specs for every listing: RAM, storage, ports, barebone."""
    blob = f"{listing.title}\n{listing.description}\n{' '.join(listing.ocr_texts)}"
    facts: list[EnrichmentFact] = []
    ram = extract_ram(blob)
    if ram:
        facts.append(EnrichmentFact(field="ram_gb", value=ram, confidence=0.7,
                                    status=FactStatus.AI_INFERRED,
                                    sources=[Evidence(type="description",
                                                      detail=f"{ram}GB RAM mentioned",
                                                      confidence=0.7)]))
    gb, kind = extract_storage(blob)
    if gb:
        facts.append(EnrichmentFact(field="storage_gb", value=gb, confidence=0.7,
                                    status=FactStatus.AI_INFERRED,
                                    sources=[Evidence(type="description",
                                                      detail=f"{gb}GB {kind or 'storage'} mentioned",
                                                      confidence=0.7)]))
        if kind:
            facts.append(EnrichmentFact(field="storage_kind", value=kind, confidence=0.8,
                                        status=FactStatus.AI_INFERRED,
                                        sources=[Evidence(type="description",
                                                          detail=f"drive kind {kind}",
                                                          confidence=0.8)]))
    ports = extract_ports(blob)
    if ports:
        facts.append(EnrichmentFact(field="ports", value="; ".join(ports), confidence=0.75,
                                    status=FactStatus.AI_INFERRED,
                                    sources=[Evidence(type="description",
                                                      detail=f"ports: {', '.join(ports)}",
                                                      confidence=0.75)]))
    if is_barebone(blob):
        facts.append(EnrichmentFact(field="barebone", value=True, confidence=0.8,
                                    status=FactStatus.AI_INFERRED,
                                    sources=[Evidence(type="description",
                                                      detail="barebone: no RAM/SSD included (add ~cost)",
                                                      confidence=0.8)]))
    is_board, socketed = board_info(blob)
    if is_board:
        facts.append(EnrichmentFact(field="board", value=True, confidence=0.9,
                                    status=FactStatus.AI_INFERRED,
                                    sources=[Evidence(type="description",
                                                      detail=("socket platform board (needs CPU+RAM) — no completion math"
                                                              if socketed else
                                                              "soldered-CPU board (DiyPerks route: needs RAM+SSD+PSU/case)"),
                                                      confidence=0.9)]))
        if not socketed:
            facts.append(EnrichmentFact(field="board_completion_eur", value=BOARD_COMPLETION_EUR,
                                        confidence=0.5,
                                        status=FactStatus.AI_INFERRED,
                                        sources=[Evidence(type="description",
                                                          detail=f"~{BOARD_COMPLETION_EUR} EUR typical to complete (RAM+SSD+PSU/case)",
                                                          confidence=0.5)]))
    return facts


# units-per-EUR deck rates (estimate, check ECB for exact). Only used when a
# listing prices in non-EUR (eBay/ricardo paths); EUR listings are untouched.
FX_PER_EUR = {"EUR": 1.0, "€": 1.0, "USD": 1.08, "$": 1.08, "CHF": 0.94,
              "GBP": 0.85, "CZK": 25.1, "PLN": 4.32, "HUF": 390.0, "RON": 4.97}


def to_eur(price: float | None, currency: str | None) -> float | None:
    if price is None:
        return None
    rate = FX_PER_EUR.get((currency or "EUR").upper(), 1.0)
    return round(price / rate, 2) if rate else price


def enrich_cpu(listing: CanonicalListing) -> list[EnrichmentFact]:
    blob = f"{listing.title}\n{listing.description}\n{' '.join(listing.ocr_texts)}"
    cpu, conf, ev, estimated, cands = resolve_cpu_with_seeds(blob)
    if not cpu:
        return []
    if estimated:
        return [EnrichmentFact(
            field="cpu", value=cpu, confidence=conf,
            status=FactStatus.AI_INFERRED,
            sources=[Evidence(type="description", detail=ev, confidence=conf)]),
            EnrichmentFact(
            field="cpu_candidates", value="; ".join(cands), confidence=0.5,
            status=FactStatus.AI_INFERRED,
            sources=[Evidence(type="description",
                              detail="tap a candidate in the drawer to set it",
                              confidence=0.5)])]
    bench = CPU_DB.get(cpu.lower())
    facts = [EnrichmentFact(field="cpu", value=cpu, confidence=conf,
                            status=FactStatus.AI_INFERRED if conf < 0.8 else FactStatus.SUPPORTED,
                            sources=[Evidence(type="description", detail=ev, confidence=conf)])]
    if bench:
        facts.append(EnrichmentFact(field="cpu_benchmark", value=bench, confidence=0.95,
                                    status=FactStatus.EXTERNAL,
                                    sources=[Evidence(type="external", detail="cpu_benchmark plugin v0.1")]))
    return facts


def offer_targets(benchmark: float | None, barebone: bool = False,
                  ram_gb: int | None = None) -> dict:
    """Max offer prices for perf-per-euro tiers (deterministic haggle guide).

    Barebone units need ~85 EUR per 16GB RAM added (user-measured street cost);
    targets shift up so the COMPLETE system still hits the tier.
    """
    if not benchmark or benchmark <= 0:
        return {}
    uplift = 0
    if barebone and not ram_gb:
        uplift = 85
    return {"pay_for_90": round(benchmark / 90 + uplift, 0),
            "pay_for_100": round(benchmark / 100 + uplift, 0),
            "pay_for_120": round(benchmark / 120 + uplift, 0),
            "barebone_uplift": uplift}


def value_score(price: float | None, benchmark: float | None,
                market_median: float | None, currency: str | None = "EUR") -> tuple[float, list[str]]:
    why: list[str] = []
    price = to_eur(price, currency)
    if price is None or price <= 0:
        return 0.5, ["no price -> neutral"]
    parts: list[float] = []
    if benchmark:
        per_euro = benchmark / price
        # normalize: 30 pts/EUR ~= great
        s = min(1.0, per_euro / 30.0)
        parts.append(s)
        why.append(f"perf/€ {per_euro:.1f} -> {s:.2f}")
    if market_median and market_median > 0:
        discount = (market_median - price) / market_median
        s = max(0.0, min(1.0, 0.5 + discount))
        parts.append(s)
        why.append(f"vs median {market_median:.0f}: {discount:+.0%} -> {s:.2f}")
    if not parts:
        return 0.5, ["no comparable -> neutral"]
    return round(sum(parts) / len(parts), 3), why


def total_cost(price: float | None, shipping_cost: float | None = 0,
               distance_km: float | None = None, cost_per_km: float = 0.0) -> float | None:
    """Total acquisition cost: item + shipping + travel. Sortable, comparable across sources."""
    if price is None:
        return None
    total = price + (shipping_cost or 0)
    if distance_km is not None:
        total += distance_km * 2 * cost_per_km  # round trip
    return round(total, 2)


def rank(final_match: float, value: float, risk: float, completeness: float,
         weights: dict | None = None) -> float:
    w = weights or {"match": 0.35, "value": 0.35, "risk": 0.2, "completeness": 0.1}
    return round(w["match"] * final_match + w["value"] * value
                 - w["risk"] * risk + w["completeness"] * completeness, 3)

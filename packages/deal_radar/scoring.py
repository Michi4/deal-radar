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


def extract_cpu(text: str) -> tuple[str | None, float, str]:
    t = text.lower()

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
    # space-form Intel: "i7 12700H", "i5 12450H", "i7 8650-U", "i5 1145G7"
    # (dash-form handled below)
    m = re.search(r"\bi\s*([3579])\s+(\d{4,5})\s*-?\s*([a-z]{0,3}\d?)", t)
    if m:
        g = f"i{m.group(1)}-{m.group(2)}{m.group(3).upper()}"
        return g, 0.7, f"mentioned '{g}'"
    # Xeon: "Xeon E-2276M", "Xeon W-10855M", "Xeon E3-1505M"
    m = re.search(r"\bxeon\s*(e[35]?-|w-)?\s*(\d{4,5}[a-z]*)\b", t)
    if m:
        g = f"Xeon {(m.group(1) or '').upper()}{m.group(2).upper()}"
        return g.strip(), 0.8, f"mentioned '{g.strip()}'"
    # bare Intel mobile/desktop: "8650U", "1145G7", "12450H", "12700".
    # 6/7/8xxx+U/H collides with AMD numbering -> decide by nearby brand context,
    # else skip (model-seed family estimate covers business lines honestly).
    m = re.search(r"\b(\d{4})\s*-?\s*(u|h)\b|\b(\d{5})\s*([a-z]{1,3})\b", t)
    if m:
        if m.group(1):
            num, suf = m.group(1), m.group(2)
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
    # "Ryzen 3 4300U", "Ryzen 5 5600G", "Ryzen 9 9950X3D" (normalized)
    m = re.search(r"ryzen\s*([3579])(?:\s+(pro))?\s*(\d{3,4}[a-z0-9]*)", t)
    if m:
        g = f"Ryzen {m.group(1)} " + ("PRO " if m.group(2) else "") \
            + re.sub(r"\s+", "", m.group(3)).upper()
        return g, 0.85, f"mentioned '{g}'"
    # bare AMD numbers: "8845HS", "R7 7840U", "7735 HS", "5600G" -> tier from 2nd
    # digit (2/3/4->Ryzen 3, 5/6->Ryzen 5, 7/8->Ryzen 7, 9->Ryzen 9).
    # Skipped when an explicit "Ryzen <tier>" prefix exists (handled above).
    if not re.search(r"ryzen\s*[3579]", t):
        m = re.search(r"\br\s*([3579])\s*(\d{4})\s*([a-z]{1,2})\b"
                      r"|\b(\d{4})\s*(hs|hx|h|u|g|ge|x3d|x|f)\b", t)
        if m:
            # RAM-speed markings are not CPUs ("PC2-5300U", "667 MHz DIMM")
            _ctx = t[max(0, m.start() - 10):m.end() + 10]
            _is_ram = bool(re.search(r"pc\d*-\d+|\d+\s*mhz|\bdimm\b|\bsodimm\b", _ctx, re.IGNORECASE))
            tier, num, suf = "", "", ""
            if not _is_ram:
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
    cpu, conf, ev = extract_cpu(blob)
    if not cpu:
        # family estimate: known model line but no exact CPU in text (e.g. "X1 Carbon Gen 6, i5").
        # Attach the base candidate as a labeled estimate so benchmark sorting works
        # approximately; the drawer offers the exact alternatives to set.
        bl = blob.lower()
        import re as _re9
        bl_nospace = _re9.sub(r"[^a-z0-9]", "", bl)
        for seed_key, cands in MODEL_CPU_SEED.items():
            hit = seed_key in bl or _re9.sub(r"[^a-z0-9]", "", seed_key) in bl_nospace
            if hit and cands:
                if any(c.lower() in bl for c in cands):
                    continue  # exact mention handled above (extract would have caught most)
                base = cands[0]
                others = ", ".join(cands[1:4])
                return [EnrichmentFact(
                    field="cpu", value=base, confidence=0.45,
                    status=FactStatus.AI_INFERRED,
                    sources=[Evidence(
                        type="description",
                        detail=f"family estimate for '{seed_key}' (could be {base}"
                               f"{', ' + others if others else ''} — set exact CPU in drawer)",
                        confidence=0.45)]),
                    EnrichmentFact(
                    field="cpu_candidates", value="; ".join(cands[:6]), confidence=0.5,
                    status=FactStatus.AI_INFERRED,
                    sources=[Evidence(type="description",
                                      detail="tap a candidate in the drawer to set it",
                                      confidence=0.5)])]
        return []
    bench = CPU_DB.get(cpu.lower())
    facts = [EnrichmentFact(field="cpu", value=cpu, confidence=conf,
                            status=FactStatus.AI_INFERRED if conf < 0.8 else FactStatus.SUPPORTED,
                            sources=[Evidence(type="description", detail=ev, confidence=conf)])]
    if bench:
        facts.append(EnrichmentFact(field="cpu_benchmark", value=bench, confidence=0.95,
                                    status=FactStatus.EXTERNAL,
                                    sources=[Evidence(type="external", detail="cpu_benchmark plugin v0.1")]))
    return facts


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

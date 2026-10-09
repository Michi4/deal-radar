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
    # space-form Intel: "i7 12700H", "i5 12450H" (dash-form handled below)
    m = re.search(r"\bi\s*([3579])\s+(\d{4,5}[a-z]{0,3})\b", t)
    if m:
        g = f"i{m.group(1)}-{m.group(2).upper()}"
        return g, 0.7, f"mentioned '{g}'"
    # explicit Ryzen with number: "Ryzen 5 PRO 5650U", "Ryzen 7 8845HS",
    # "Ryzen 3 4300U", "Ryzen 5 5600G" (normalized)
    m = re.search(r"ryzen\s*([3579])(?:\s+(pro))?\s*(\d{3,4}\s*[a-z]*)", t)
    if m:
        g = f"Ryzen {m.group(1)} " + ("PRO " if m.group(2) else "") \
            + re.sub(r"\s+", "", m.group(3)).upper()
        return g, 0.85, f"mentioned '{g}'"
    # bare AMD numbers: "8845HS", "R7 7840U", "7735 HS", "5600G" -> tier from 2nd
    # digit (2/3/4->Ryzen 3, 5/6->Ryzen 5, 7/8->Ryzen 7, 9->Ryzen 9).
    # Skipped when an explicit "Ryzen <tier>" prefix exists (handled above).
    if not re.search(r"ryzen\s*[3579]", t):
        m = re.search(r"\br\s*([3579])\s*(\d{4})\s*([a-z]{1,2})\b"
                      r"|\b(\d{4})\s*(hs|hx|h|u|g|ge)\b", t)
        if m:
            if m.group(1):
                tier, num, suf = m.group(1), m.group(2), m.group(3)
            else:
                num, suf = m.group(4), m.group(5)
                tier = {"2": "3", "3": "3", "4": "3", "5": "5", "6": "5",
                        "7": "7", "8": "7", "9": "9"}.get(num[1], "")
            if tier and suf in ("h", "hs", "hx", "u", "g", "ge"):
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
        return []
    return [EnrichmentFact(field="gpu", value=gpu, confidence=conf,
                           status=FactStatus.AI_INFERRED if conf < 0.85 else FactStatus.SUPPORTED,
                           sources=[Evidence(type="description", detail=ev, confidence=conf)])]


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
                market_median: float | None) -> tuple[float, list[str]]:
    why: list[str] = []
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

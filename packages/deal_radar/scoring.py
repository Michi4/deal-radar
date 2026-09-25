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
    "thinkpad t14 gen 2": ["Ryzen 5 PRO 5650U", "Ryzen 7 PRO 5850U", "i5-1135G7", "i7-1165G7"],
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
    for cpu in CPU_DB:
        if cpu in t:
            return cpu, 0.9, f"mentioned '{cpu}'"
    m = re.search(r"(ryzen\s*\d+\s*\w*|i[3579]-\d{4,5}\w*|m[1-4](\s*pro|\s*max)?)", t)
    if m:
        return m.group(1).strip(), 0.45, f"pattern '{m.group(1)}' (unverified)"
    return None, 0.0, ""


GPU_PATS = [
    r"rtx\s*\d{3,4}(?:\s*ti)?(?:\s*super)?(?:\s*laptop)?",
    r"rx\s*\d{3,4}(?:\s*m|\s*xt)?",
    r"gtx\s*\d{3,4}(?:\s*ti)?(?:\s*super)?",
    r"rtx\s*a\d{3,4}",
    r"quadro\s*\w+\d+",
    r"arc\s*a\d{3}",
]


def extract_gpu(text: str) -> tuple[str | None, float, str]:
    t = text.lower()
    for pat in GPU_PATS:
        m = re.search(pat, t)
        if m:
            g = re.sub(r"\s+", " ", m.group(0)).strip()
            full = len(re.findall(r"\d", g)) >= 3
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

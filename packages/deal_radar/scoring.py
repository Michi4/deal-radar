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


def extract_cpu(text: str) -> tuple[str | None, float, str]:
    t = text.lower()
    for cpu in CPU_DB:
        if cpu in t:
            return cpu, 0.9, f"mentioned '{cpu}'"
    m = re.search(r"(ryzen\s*\d+\s*\w*|i[3579]-\d{4,5}\w*|m[1-4](\s*pro|\s*max)?)", t)
    if m:
        return m.group(1).strip(), 0.45, f"pattern '{m.group(1)}' (unverified)"
    return None, 0.0, ""


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

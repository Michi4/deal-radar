"""Enrichment fabric: every enricher implements one interface. Register new ones without touching core.

class MyEnricher(Enricher):
    id = "my-source"; version = "0.1.0"
    def supports(self, listing) -> bool: ...
    def enrich(self, listing, ctx) -> list[EnrichmentFact]: ...   # ctx: {"results": [...], "median": ...}
register(MyEnricher())
Builtins: cpu_benchmark (PassMark, external w/ static fallback), market_cohort (internal stats).
"""
from __future__ import annotations
from typing import Any
from .contracts import CanonicalListing, EnrichmentFact, FactStatus, Evidence

REGISTRY: dict[str, "Enricher"] = {}


class Enricher:
    id: str = "base"
    version: str = "0.0.0"

    def supports(self, listing: CanonicalListing) -> bool:
        return True

    def enrich(self, listing: CanonicalListing, ctx: dict[str, Any]) -> list[EnrichmentFact]:
        raise NotImplementedError


def register(e: Enricher) -> None:
    REGISTRY[e.id] = e


class MarketCohortEnricher(Enricher):
    """Internal: position of this listing vs the live result cohort (median/min/count/discount)."""
    id = "market_cohort"
    version = "0.1.0"

    def supports(self, listing: CanonicalListing) -> bool:
        return listing.price is not None

    def enrich(self, listing: CanonicalListing, ctx: dict[str, Any]) -> list[EnrichmentFact]:
        prices = [p for p in ctx.get("prices", []) if p]
        if not prices or listing.price is None:
            return []
        import statistics
        med = statistics.median(prices)
        disc = (med - listing.price) / med if med > 0 else 0
        return [
            EnrichmentFact(field="market_median", value=round(med, 2), confidence=0.9,
                           status=FactStatus.EXTERNAL,
                           sources=[Evidence(type="external", detail=f"live cohort n={len(prices)}")]),
            EnrichmentFact(field="discount_vs_median", value=round(disc, 3), confidence=0.9,
                           status=FactStatus.EXTERNAL,
                           sources=[Evidence(type="external", detail=f"price {listing.price} vs median {med:.0f}")]),
        ]


register(MarketCohortEnricher())

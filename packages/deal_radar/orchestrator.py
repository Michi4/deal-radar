"""Orchestrator: many sources, one pipeline. Deterministic core + AI workers inside.

Pipeline per listing: dedupe -> hard/black/white filter -> Stage A heuristic ->
risk assess -> enrichment -> value/rank -> policy lane -> store+events -> notify.
Stage B (Jev/Kev/vision) only for borderline listings to stay fast + cheap.
Generic over verticals: intent DSL drives products, jobs, real estate, anything.
"""
from __future__ import annotations
import asyncio
import os
import statistics
import time
from typing import Any

from .contracts import ScoredListing
from .driver_sdk import DriverRegistry, SearchQuery
from .filter_engine import apply_filters
from .risk_engine import assess_risk, apply_risk_policy
from .scoring import enrich_cpu, value_score, rank
from .decision import heuristic_decide, jev_decide, kev_decide, STAGE_B_QUESTIONS, stage_b_to_scores
from . import metrics


def dedupe_key(title: str, images: list[str]) -> str:
    import re
    norm = re.sub(r"[^a-z0-9]+", "", title.lower())[:48]
    img = (images[0].split("?")[0][-40:]) if images else "noimg"
    return f"{norm}|{img}"


async def run_search(intent: dict[str, Any], registry: DriverRegistry,
                     store=None, notifier=None) -> dict[str, Any]:
    t0 = time.time()
    sources: list[str] = intent.get("sources", registry.ids())
    q = SearchQuery(keywords=intent.get("keywords", ""), category=intent.get("category", ""),
                    max_price=(intent.get("hard") or {}).get("max_price"),
                    min_price=(intent.get("hard") or {}).get("min_price"),
                    limit=int(intent.get("limit", 20)))
    hard = intent.get("hard", {})
    blacklist = intent.get("blacklist", [])
    whitelist = intent.get("whitelist", [])
    risk_policy = intent.get("risk", {})
    weights = intent.get("ranking", None)

    # 1. fan-out to drivers (multi-select), each guarded (retry+breaker, never raises)
    async def one(source: str):
        d = registry.get(source)
        if d is None:
            return source, [], f"driver '{source}' not installed"
        t = time.time()
        res, err = await d.guarded_search(q)
        metrics.observe_latency(f"driver_{source}", time.time() - t)
        metrics.inc(f"driver_{source}_fetched", len(res))
        if err:
            metrics.inc(f"driver_{source}_errors")
        return source, res, err

    results = await asyncio.gather(*(one(s) for s in sources))
    all_listings = [l for _, ls, _ in results for l in ls]
    driver_errors = {s: e for s, _, e in results if e}
    metrics.inc("listings_fetched", len(all_listings))

    # market median for risk/value context
    prices = sorted(l.price for l in all_listings if l.price)
    median = statistics.median(prices) if len(prices) >= 3 else None
    if median:
        metrics.set_gauge("market_median", median)

    seen: set[str] = set()
    scored: list[ScoredListing] = []
    filtered_out = 0
    events: list[dict] = []

    jev_key = os.getenv("JEV_API_KEY", "")
    use_stage_b = bool(os.getenv("JEV_API_KEY") or os.getenv("KEV_URL"))

    for l in all_listings:
        key = dedupe_key(l.title, l.images)
        if key in seen:
            metrics.inc("duplicates")
            continue
        seen.add(key)

        fr = apply_filters(l, hard, blacklist, whitelist)
        if not fr.passed:
            filtered_out += 1
            metrics.inc("listings_filtered")
            continue

        h = heuristic_decide(l.title, l.description, l.price, q.keywords)
        metrics.inc("stage_a_total")

        r = assess_risk(l, median)
        enrich = enrich_cpu(l) if intent.get("enrich", True) else []
        bench = next((e.value for e in enrich if e.field == "cpu_benchmark"), None)
        val, val_why = value_score(l.price, bench, median)
        completeness = min(1.0, (bool(l.title) + bool(l.description and len(l.description) > 50)
                                  + bool(l.images) + bool(l.price)) / 4.0)
        lane = apply_risk_policy(r, val, risk_policy)
        final = rank(h["match"], val, r.score, completeness, weights)

        dna = {"match": h["match"], "value": val, "risk": r.score,
               "completeness": round(completeness, 3), "condition": 0.5, "confidence": r.confidence}
        why = [*fr.reasons, *val_why, *(f"risk: {x}" for x in r.reasons),
               *(f"ok: {x}" for x in r.counter_evidence)]

        # Stage B escalation: borderline/high-value only
        if use_stage_b and (h["needs_stage_b"] or (val >= 0.8 and r.score >= 0.3)):
            metrics.inc("stage_b_total")
            state = {"title": l.title, "description": (l.description or "")[:2000],
                     "price": l.price, "images": len(l.images), "ocr": l.ocr_texts[:3]}
            ans = await jev_decide(state, STAGE_B_QUESTIONS, api_key=jev_key) if jev_key \
                else await kev_decide(state, STAGE_B_QUESTIONS)
            sb = stage_b_to_scores(ans)
            if sb:
                if "exact" in sb:
                    dna["match"] = round(0.5 * dna["match"] + 0.5 * sb["exact"], 3)
                if "risk_ai" in sb:
                    r.score = round(0.6 * r.score + 0.4 * sb["risk_ai"], 3)
                    dna["risk"] = r.score
                if "condition_ai" in sb:
                    dna["condition"] = round(sb["condition_ai"], 3)
                why.append("stage-B (Jev/Kev) verification applied")
                final = rank(dna["match"], val, r.score, completeness, weights)
                lane = apply_risk_policy(r, val, risk_policy)

        s = ScoredListing(listing=l, match_score=h["match"], deal_dna=dna, risk=r,
                          enrichments=enrich, value_score=val, final_score=final, lane=lane, why=why)
        scored.append(s)
        if store is not None:
            ch = store.upsert(l)
            for c in ch:
                ev = {"listing_id": l.id, "url": l.url, "title": l.title, **c}
                events.append(ev)
                if notifier and c["kind"] == "price":
                    await notifier.send(f"Price change: {l.title[:60]}",
                                        f"{c['old']} -> {c['new']} {l.currency} :: {l.url}", ev)

    scored.sort(key=lambda s: s.final_score, reverse=True)
    metrics.inc("listings_scored", len(scored))
    metrics.observe_latency("search", time.time() - t0)
    metrics.set_gauge("last_search_results", len(scored))
    return {"results": [s.model_dump() for s in scored], "events": events,
            "driver_errors": driver_errors, "filtered_out": filtered_out,
            "median": median, "sources": sources}

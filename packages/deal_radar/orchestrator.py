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

from . import metrics
from .contracts import EnrichmentFact, Evidence, FactStatus, ScoredListing
from .decision import (
    STAGE_B_QUESTIONS,
    heuristic_decide,
    jev_decide,
    kev_decide,
    stage_b_to_scores,
    stage_b_via_cloud,
)
from .driver_sdk import DriverRegistry, SearchQuery
from .filter_engine import apply_filters
from .risk_engine import apply_risk_policy, assess_risk
from .scoring import enrich_cpu, rank, value_score


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
    hard = intent.get("hard", {}) or {}
    if isinstance(hard, list):  # model sometimes returns bare rules list
        hard = {"rules": hard}
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

    results = await asyncio.gather(*(one(src) for src in sources))
    all_listings = [l for _, ls, _ in results for l in ls]
    driver_errors = {src: e for src, _, e in results if e}
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
    _vision_queue: list = []
    _stageb_queue: list = []

    jev_key = os.getenv("JEV_API_KEY", "")
    use_stage_b = bool(os.getenv("JEV_API_KEY") or os.getenv("KEV_URL") or os.getenv("CLOUD_API_KEY"))
    want_attrs: dict = intent.get("attributes", {}) or {}

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

        # product-model gate (NL product intel): listing must match one resolved model
        want_models: list[str] = intent.get("models", []) or []
        if want_models and l.title:
            import re as _re
            norm = _re.sub(r"[^a-z0-9]+", "", l.title.lower())
            if not any(_re.sub(r"[^a-z0-9]+", "", m.lower()) in norm for m in want_models):
                filtered_out += 1
                metrics.inc("listings_filtered_model")
                continue

        h = heuristic_decide(l.title, l.description, l.price, q.keywords)
        metrics.inc("stage_a_total")
        want_ad_note = ""
        if h.get("want_ad"):
            want_ad_note = "buy-request ad (Ankauf/Suche), demoted"
        elif h.get("parts_ad"):
            want_ad_note = "parts/repair ad, demoted"

        # NL attribute requirements (e.g. connector:usb-c): soft gate, evidence-logged
        attr_hits: list[str] = []
        if want_attrs:
            hay = l.field_text("all_text").lower()
            for k, v in want_attrs.items():
                if str(v).lower() in hay:
                    attr_hits.append(f"{k}={v} confirmed in listing")
                    h["match"] = min(1.0, h["match"] + 0.15)
                else:
                    attr_hits.append(f"{k}={v} NOT found (unverified, kept with penalty)")
                    h["match"] = max(0.0, h["match"] - 0.1)

        r = assess_risk(l, median)
        enrich = enrich_cpu(l) if intent.get("enrich", True) else []
        # OCR listing photos (best-effort, cached) so spec stickers/BIOS screens become searchable text
        if intent.get("ocr", True) and l.images and not l.ocr_texts:
            try:
                from .vision import ocr_listing_images
                l.ocr_texts = await asyncio.to_thread(ocr_listing_images, l.images, 1)
                if l.ocr_texts:
                    metrics.inc("ocr_texts")
                    enrich = enrich_cpu(l)  # re-extract (CPU may only be visible in photos)
            except Exception:
                pass
        # CPU identification: override > direct mention > model-family resolution.
        # Runs whenever enrichment is on (independent of benchmark lookup).
        bn_why: list[str] = []
        cpu_fact = next((e for e in enrich if e.field == "cpu"), None)
        override = None
        if intent.get("enrich", True):
            # manual override wins (user-corrected in the drawer; AI-checked below)
            override = (store.get_facts(l.id).get("cpu") if store else None) if intent.get("overrides", True) else None
            if override:
                cpu_fact = EnrichmentFact(field="cpu", value=override, confidence=1.0,
                                          status=FactStatus.VERIFIED,
                                          sources=[Evidence(type="description", detail="user-corrected")])
                enrich = [e for e in enrich if e.field not in ("cpu", "cpu_benchmark")] + [cpu_fact]
                bn_why.append(f"CPU manually set to {override} (AI-checking against PassMark)")
            # model-family resolution: "hp 835 g8" -> candidate CPUs -> disambiguate from text/photos
            if not cpu_fact and want_models:
                try:
                    from .scoring import resolve_cpu_candidates
                    blob = f"{l.title}\n{l.description}\n{' '.join(l.ocr_texts)}".lower()
                    for model in want_models[:3]:
                        cands = await resolve_cpu_candidates(model)
                        hit = next((c for c in cands if c.lower() in blob), None)
                        if hit:
                            cpu_fact = EnrichmentFact(field="cpu", value=hit, confidence=0.7,
                                                      status=FactStatus.AI_INFERRED,
                                                      sources=[Evidence(type="description", detail=f"resolved for {model}")])
                            enrich = [e for e in enrich if e.field not in ("cpu",)] + [cpu_fact]
                            bn_why.append(f"CPU {hit} inferred for {model}")
                            break
                    if not cpu_fact:
                        bn_why.append("CPU unknown for this model — open the drawer to set it manually")
                        metrics.inc("cpu_unresolved")
                except Exception:
                    pass
            # contradiction: title names a different known CPU than resolved
            if cpu_fact:
                try:
                    from .scoring import extract_cpu as _xc
                    other, conf, _ = _xc(f"{l.title}".lower())
                    if other and other.lower() != str(cpu_fact.value).lower() and conf >= 0.8:
                        bn_why.append(f"CONTRADICTION: title says {other} but resolved {cpu_fact.value}")
                        metrics.inc("cpu_contradicted")
                        r.score = min(1.0, r.score + 0.2)
                except Exception:
                    pass
        # upgrade static benchmark to real PassMark scores (disk-cached, gentle 1 req/s)
        if intent.get("benchmarks", True) and cpu_fact:
            try:
                from .benchmarks import fetch_passmark_cpu
                real = await asyncio.to_thread(fetch_passmark_cpu, str(cpu_fact.value))
                if real:
                    enrich = [e for e in enrich if e.field not in ("cpu_benchmark",)]
                    enrich.append(EnrichmentFact(field="cpu_benchmark", value=real["multi"], confidence=0.97,
                                                 status=FactStatus.EXTERNAL,
                                                 sources=[Evidence(type="external", detail="cpubenchmark.net")]))
                    for sf in ("single", "class", "socket", "clockspeed", "turbo", "tdp", "cores",
                               "threads", "cache_l1i", "cache_l1d", "cache_l2", "cache_l3",
                               "rank_mt", "rank_st", "first_seen", "samples"):
                        if real.get(sf) is not None:
                            enrich.append(EnrichmentFact(field=f"cpu_{sf}", value=real[sf], confidence=0.95,
                                                         status=FactStatus.EXTERNAL,
                                                         sources=[Evidence(type="external", detail="cpubenchmark.net")]))
                    metrics.inc("benchmark_real")
                    if override:
                        cpu_fact.status = FactStatus.VERIFIED
                        bn_why.append(f"AI-check: {override} exists on PassMark \u2713")
                else:
                    metrics.inc("benchmark_static_fallback")
                    if override:
                        bn_why.append(f"AI-check: {override} NOT found on PassMark (unverified)")
            except Exception:
                pass
        bench = next((e.value for e in enrich if e.field == "cpu_benchmark"), None)
        val, val_why = value_score(l.price, bench, median)
        completeness = min(1.0, (bool(l.title) + bool(l.description and len(l.description) > 50)
                                  + bool(l.images) + bool(l.price)) / 4.0)
        lane = apply_risk_policy(r, val, risk_policy)
        final = rank(h["match"], val, r.score, completeness, weights)

        dna = {"match": h["match"], "value": val, "risk": r.score,
               "completeness": round(completeness, 3), "condition": 0.5, "confidence": r.confidence}
        why = [*fr.reasons, *val_why, *attr_hits, *(f"risk: {x}" for x in r.reasons),
               *(f"ok: {x}" for x in r.counter_evidence)]
        why.extend(bn_why)
        if want_ad_note:
            why.append(want_ad_note)

        s = ScoredListing(listing=l, match_score=h["match"], deal_dna=dna, risk=r,
                          enrichments=enrich, value_score=val, final_score=final, lane=lane, why=why)
        # Stage B + vision run concurrently after the loop (Kev/VLM are the slow step — never sequential)
        if use_stage_b and (h["needs_stage_b"] or (val >= 0.8 and r.score >= 0.3)):
            _stageb_queue.append((s, h, q.keywords))
        # vision check (VLM): only Stage-B listings with photos — collected, run concurrently after loop
        if intent.get("vision", True) and l.images and h.get("needs_stage_b"):
            _vision_queue.append(s)
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
    # Stage B concurrent pass (cap: most uncertain first; sem bounds slow-model load)
    if _stageb_queue:
        _stageb_queue.sort(key=lambda t: abs(t[1].get("match", 0.5) - 0.55))
        _sb_sem = asyncio.Semaphore(2)  # Frankfurt Kev is 2 shared vCPUs — gentle

        async def _sb(item):
            sc, _h, keywords = item
            sb: dict = {}
            try:
                async with _sb_sem:
                    metrics.inc("stage_b_total")
                    l = sc.listing
                    state = {"title": l.title, "description": (l.description or "")[:2000],
                             "price": l.price, "images": len(l.images), "ocr": l.ocr_texts[:3]}
                    ans = await jev_decide(state, STAGE_B_QUESTIONS, api_key=jev_key) if jev_key \
                        else await kev_decide(state, STAGE_B_QUESTIONS)
                    sb = stage_b_to_scores(ans)
                    if not sb and os.getenv("CLOUD_API_KEY"):
                        metrics.inc("stage_b_cloud")
                        sb = await stage_b_via_cloud(l.title, l.description, l.price, keywords)
            except Exception:
                sb = {}
            if not sb:
                return
            if sb.get("note"):
                sc.why.append(f"cloud: {sb['note']}")
            if "exact" in sb:
                sc.deal_dna["match"] = round(0.5 * sc.deal_dna.get("match", sc.match_score) + 0.5 * sb["exact"], 3)
            if "risk_ai" in sb:
                sc.risk.score = round(0.6 * sc.risk.score + 0.4 * sb["risk_ai"], 3)
                sc.deal_dna["risk"] = sc.risk.score
            if "condition_ai" in sb:
                sc.deal_dna["condition"] = round(sb["condition_ai"], 3)
            sc.why.append("stage-B (Jev/Kev) verification applied")

        await asyncio.gather(*(_sb(it) for it in _stageb_queue[:12]))  # bound cost
        for s in scored:
            s.final_score = rank(s.deal_dna.get("match", s.match_score), s.value_score, s.risk.score,
                                 s.deal_dna.get("completeness", 0.5), intent.get("ranking", None))
            s.lane = apply_risk_policy(s.risk, s.value_score, intent.get("risk", {}))
        scored.sort(key=lambda s: s.final_score, reverse=True)
    # lazy detail enrichment: full description + seller age for top results (feeds risk + CPU extraction)
    if intent.get("details", True):
        async def _det(s):
            d = registry.get(s.listing.source)
            if d is None or "fetch_detail" not in (d.manifest.capabilities or []):
                return
            try:
                det = await d.fetch_detail(s.listing.native_id or s.listing.url)
            except Exception:
                det = None
            if not det:
                return
            metrics.inc("detail_enriched")
            if det.description and len(det.description) > len(s.listing.description or ""):
                s.listing.description = det.description
            if det.price and not s.listing.price:
                s.listing.price = det.price
            if det.seller and det.seller.name and not s.listing.seller.name:
                s.listing.seller.name = det.seller.name
            if det.seller and det.seller.account_age_days is not None:
                s.listing.seller.account_age_days = det.seller.account_age_days
            if det.location and not s.listing.location:
                s.listing.location = det.location
            if det.attributes:
                s.listing.attributes.update(det.attributes)
            # re-extract CPU + re-assess risk with the full text
            try:
                cpu2 = enrich_cpu(s.listing)
                if cpu2:
                    s.enrichments = [e for e in s.enrichments if e.field not in ("cpu", "cpu_benchmark")] + cpu2
                r2 = assess_risk(s.listing, median)
                s.risk = r2
                s.final_score = rank(s.match_score, s.value_score, r2.score,
                                     s.deal_dna.get("completeness", 0.5), intent.get("ranking", None))
                s.why.append("detail page enriched (full text + seller)")
            except Exception:
                pass

        await asyncio.gather(*(_det(s) for s in scored[:3]))
        scored.sort(key=lambda s: s.final_score, reverse=True)
    # concurrent vision pass over Stage-B candidates (each is slow on CPU — parallelize)
    if _vision_queue:
        from .vision import vision_check

        async def _one(s):
            try:
                async with _vision_sem:
                    vc = await vision_check(s.listing.images[0], s.listing.title, s.listing.description)
            except Exception:
                vc = {}
            if not vc:
                return
            metrics.inc("vision_total")
            s.deal_dna["visual_consistency"] = round(vc.get("shows_item", 0.5), 3)
            if vc.get("is_stock", 0) >= 0.7:
                s.risk.score = min(1.0, s.risk.score + 0.15)
                s.why.append("vision: looks like a stock photo (+risk)")
            if vc.get("shows_item", 1) < 0.4:
                s.deal_dna["match"] = round(s.deal_dna.get("match", s.match_score) * 0.6, 3)
                s.why.append(f"vision: photo may not show the item ({vc.get('note', '')})")
            else:
                s.why.append(f"vision: photo consistent ({vc.get('note', '')})")
            if vc.get("visible_text"):
                s.listing.ocr_texts = [*s.listing.ocr_texts, f"VLM: {vc['visible_text']}"[:500]]

        _vision_sem = asyncio.Semaphore(1)  # VLM on laptop CPU is ~100s/call — strictly serial
        _vision_queue.sort(key=lambda s: s.final_score, reverse=True)
        await asyncio.gather(*(_one(it) for it in _vision_queue[:3]))  # hard cap: top-3 only
        for s in scored:  # re-rank after vision evidence
            s.final_score = rank(s.match_score, s.value_score, s.risk.score,
                                 s.deal_dna.get("completeness", 0.5),
                                 intent.get("ranking", None))
            s.lane = apply_risk_policy(s.risk, s.value_score, intent.get("risk", {}))
        scored.sort(key=lambda s: s.final_score, reverse=True)
    # enrichment-fabric second stage: cohort facts for every scored listing
    try:
        from .enrich import REGISTRY
        ctx = {"prices": [s.listing.price for s in scored if s.listing.price],
               "median": median, "sources": sources}
        for s in scored:
            for enr in REGISTRY.values():
                try:
                    if enr.supports(s.listing):
                        s.enrichments.extend(enr.enrich(s.listing, ctx))
                except Exception:
                    continue
    except Exception:
        pass
    # cross-listing same-item detection (same photo hash on multiple sources; capped for speed)
    try:
        if len({s.listing.source for s in scored}) > 1:
            from .imgdup import find_dupes, image_hash
            cand = [s for s in scored if s.listing.images][:12]
            hashes = {s.listing.id: image_hash(s.listing.images[0]) for s in cand}
        for a, b, dist in find_dupes(hashes):
            metrics.inc("duplicates_cross_source")
            for s_item in scored:
                if s_item.listing.id in (a, b):
                    dup_other = next(x for x in scored if x.listing.id == (b if s_item.listing.id == a else a))
                    s_item.why.append(f"same item also on {dup_other.listing.source} "
                                      f"for {dup_other.listing.price} {dup_other.listing.currency} (img-dist {dist})")
    except Exception:
        pass
    metrics.inc("listings_scored", len(scored))
    metrics.inc("search_runs")
    metrics.observe_latency("search", time.time() - t0)
    metrics.set_gauge("last_search_results", len(scored))
    return {"results": [s.model_dump() for s in scored], "events": events,
            "driver_errors": driver_errors, "filtered_out": filtered_out,
            "median": median, "sources": sources}

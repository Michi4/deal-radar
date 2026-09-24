# deal-radar — AI-driven used-products finder & comparer (live, self-hostable)

> Deterministic event-driven core + swappable AI workers + hot-swappable marketplace drivers.
> Deals are vertical #1. The engine is generic: products, jobs, housing, anything with listings.

## Quickstart
```bash
pip install -e ".[test]"
PYTHONPATH=packages:drivers pytest -q
PYTHONPATH=packages:drivers:apps uvicorn api.main:app --port 8099 --app-dir apps
# open http://localhost:8099
```

## Sources / drivers
| driver | access | status |
|---|---|---|
| ebay | official Browse API (`EBAY_OAUTH_TOKEN`, `EBAY_MARKETPLACE=EBAY_AT`) | reference driver, permitted |
| willhaben | public web (personal hobbyist use; ToS restrict bots — use gently, proxy optional) | polling, fixture-tested parser |
| kleinanzeigen | public web (same caveat) | polling, fixture-tested parser |

Add a driver: copy `drivers/_template/`, implement `search()`, add manifest, register in `apps/api/main.py`.
`TRANSPORTS_JSON='{"willhaben":{"type":"proxy","url":"http://user:pass@host:port"}}'` swaps direct/proxy/rotating per driver without touching driver code.

## AI cascade (fast + cheap by default)
- **Stage A (every listing):** heuristic match + deterministic risk signals. µs, offline.
- **Stage B (borderline/high-value only):** Jev (`JEV_API_KEY`) or Kev self-hosted (`KEV_URL`, same SystemOne API) verifies exact-product, image/description consistency, risk, condition.
- Vision/OCR hooks: `ocr_texts` + `images` fields flow into every stage; wire PaddleOCR/Qwen-VL as workers later.

## Key behaviors
- Scam = **percentage + evidence**, never boolean. Default = flag/sort-down; hard-hide only if `risk.hard_filter_enabled` + over `block_threshold`. Great deals go to **review lane**, never silently dropped.
- Filters per field (`title|description|tags|category|seller_name|location|condition|ocr|attributes.*|price`): contains/not_contains/regex/equals/lt/gt/range/in. **Missing fields → rule N/A → pass**, never error.
- Live: SSE `/stream` pushes price/desc/image change events; store keeps **immutable observations** + favorites; notify via ntfy (`NTFY_TOPIC_URL`) / webhook / log.
- Metrics: `/metrics` (Prometheus) — driver latency/errors, pipeline counts, AI stage counts, market median.
- Enrichment: `enrich_cpu()` demo (infers CPU incl. from OCR text → benchmark → perf/€ ranking). Same interface generalizes to GPU/phone/battery/etc.

## Repo hygiene
Conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`). Contract tests per driver with recorded fixtures.

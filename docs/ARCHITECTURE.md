# Architecture (v0.1) — generic live-search engine, deals first

```
intent DSL -> orchestrator -> drivers (ebay|willhaben|kleinanzeigen|...) [guarded: retry+breaker+proxy]
  -> dedupe -> filter engine (per-field hard/black/white; missing=N/A)
  -> Stage A heuristic -> risk % + evidence -> enrichment (cpu bench, ...) -> value/rank
  -> Stage B Jev/Kev (borderline only) -> policy lane (top|good|review|risky|hidden)
  -> store (immutable observations) -> SSE live + notifier -> PWA
```

- Evidence-first: facts carry status (seller_stated|inferred|ocr|external|verified) + confidence + sources.
- Verticals: replace keywords/category/attributes + enrichment plugins; pipeline unchanged (jobs, housing, cameras...).
- Observability: /metrics exposes driver latency/errors, pipeline counters, AI stage counts.
- Failure model: SOURCE_UNAVAILABLE|RATE_LIMITED|SCHEMA_CHANGED|PARSER_FAILED|TIMEOUT|CAPTCHA... ->
  retry once -> mark degraded (breaker) -> continue other sources -> report in `driver_errors`.
```

# Search DSL (intent)
```yaml
keywords: "ThinkPad T14 Ryzen"
sources: [willhaben, kleinanzeigen, ebay]
hard: {max_price: 700, rules: [{fields: [title, description], op: not_regex, value: "defekt|bastler"}]}
blacklist: [{fields: [title], op: not_contains, value: "für Teile"}]
whitelist: []
risk: {warning_threshold: 0.35, block_threshold: 0.85, hard_filter_enabled: false,
       never_block_without_hard_signal: true}
ranking: {match: 0.35, value: 0.35, risk: 0.2, completeness: 0.1}
enrich: true
limit: 20
```

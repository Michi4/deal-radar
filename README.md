# deal-radar — AI-driven used-products finder & comparer (live, self-hostable)

> Deterministic event-driven core + swappable AI workers + hot-swappable marketplace drivers.
> Deals are vertical #1. The engine is generic: products, jobs, housing, anything with listings.

## Quickstart
```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[test]"
PYTHONPATH=packages:drivers .venv/bin/python -m pytest -q
PYTHONPATH=packages:drivers:apps .venv/bin/python -m uvicorn api.main:app --port 8099 --app-dir apps
# open http://localhost:8099  (E2E: node tests/e2e/run.mjs, needs headless chromium)
```

## Sources / drivers
| driver | access | status |
|---|---|---|
| ebay | official Browse API (`EBAY_OAUTH_TOKEN`) | implemented, needs token (clean error until then) |
| willhaben | public web (personal hobbyist use; ToS restrict bots — ≤1 req/s) | search (`__NEXT_DATA__`) + detail (seller age, full desc), fixture-tested |
| kleinanzeigen | public web (same caveat) | search (live layout, DHL badges) + detail (attrs, price, images), fixture-tested |

Add a driver: follow `docs/DRIVER_AUTHORING.md`. `TRANSPORTS_JSON` swaps direct/proxy/rotating
per driver without touching driver code. Registry: `PYTHONPATH=packages python -m deal_radar.registry list|check|install`.

## AI cascade (fast + cheap by default)
- **Stage A (every listing):** heuristic match + kind classifier (offer/want/parts) + deterministic risk signals. µs, offline.
- **Stage B (borderline/high-value only):** Kev (`KEV_URL`, self-hosted, SystemOne API) → cloud model (`CLOUD_*`, OpenAI-compatible, local-first via `LOCAL_API_URL` Ollama) verifies exact-product, risk, condition.
- **NL search** (`POST /searches/nl`): AI resolves product models (e.g. USB-C iPhones → 15/16/17) → per-model fan-out → merged ranked results. Offline fallback + 7-day intent cache.
- **Vision:** tesseract OCR on photos + VLM photo↔description consistency (`LOCAL_MODEL_VISION`), concurrent bounded pass.
- **Enrichment fabric** (`packages/deal_radar/enrich.py`): CPU→real PassMark scores, market-cohort stats, cross-source image-dupe hints.

## Environment (required vs optional)
| var | required? | without it |
|---|---|---|
| (none) | — | app runs: search, filters, risk %, favorites, watches work offline |
| `EBAY_OAUTH_TOKEN` | no | ebay driver clean-errors, excluded from defaults |
| `CLOUD_API_URL` + `CLOUD_API_KEY` | no | NL falls back to deterministic parser; Stage B uses Kev/heuristics |
| `KEV_URL` | no | Stage B uses cloud/heuristic fallback |
| `LOCAL_API_URL` / `LOCAL_MODEL_VISION` | no | NL/vision via cloud or skipped fast (breaker) |
| `SIGNAL_NUMBER` / `NTFY_TOPIC_URL` / `WEBHOOK_URL` | no | alerts log only |
| `API_KEY`, `RATE_PER_MIN` | no | open + 120/min default (set behind Authelia in prod) |
| `LAB_ENABLED`, `GH_TOKEN`/`LAB_PUBLISH` | no | AI Lab + PR publishing stay off |

## Key behaviors
- Scam = **percentage + evidence**, never boolean. Default = flag/sort-down; hard-hide only if `risk.hard_filter_enabled` + over `block_threshold`. Great deals go to **review lane**, never silently dropped.
- Filters per field (`title|description|tags|category|seller_name|location|postcode|shipping|condition|ocr|attributes.*|price|distance_km|shipping_cost|pickup|shipping_available`): contains/not_contains/regex/equals/lt/gt/range/in/exists. **Missing fields → rule N/A → pass**, never error.
- Live: watched searches re-poll (persisted in sqlite, survive restarts); SSE `/stream` pushes new matches + price/desc/image changes; notify via Signal/Telegram/email/ntfy/webhook/log fan-out.
- Metrics: `/metrics` (text) + `/metrics.json` + `/admin` panel — driver latency/errors/health, pipeline + AI stage counts.
- Enrichment: CPU→PassMark→perf/€ ranking, market median/discount facts, same-item-on-X hints.

## Deploy
- Homeserver (primary): `deploy/homeserver/` (Traefik websecure + Authelia), `dealradar.home.websters.at`.
- AI brains (verified live 2026-09-26): Kev-0.8B on **Frankfurt** (systemd, WG `10.8.1.1:8001`, answers <2s);
  NL text via laptop Ollama qwen2.5:3b (`LOCAL_API_URL`, 192.168.1.172:11434); vision via laptop qwen2.5vl:3b
  (`LOCAL_VISION_API_URL`); OpenRouter-free last resort. Order: local → OpenRouter → deterministic
  heuristics. Everything degrades gracefully: no keys/models = heuristics + parsers, still fully working.
- Full env reference: `deploy/homeserver/.env.sample` (secrets stay in server `.env`, never git).
- Back up sqlite: `sqlite3 /data/dealradar.db ".backup '/backups/dealradar-$(date +%F).db'"` on cron.

## Fair-use / ToS note
Willhaben, Kleinanzeigen and eBay prohibit unauthorized automated access in their terms.
This tool is built for personal, low-volume hobbyist use (≤1 req/s, cached, polite).
Running it at scale, republishing scraped data, or inviting heavy third-party use may violate
those terms and get IPs/accounts blocked. You assume that risk; keep it gentle.

## Repo hygiene
Conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`). Contract + fixture tests per driver. Autonomous rules: `AGENTS.md`, checklist `ACCEPTANCE.md`, blocks `BLOCKERS.md`, decisions `DECISIONS.md`, verify via `./scripts/verify.sh`.

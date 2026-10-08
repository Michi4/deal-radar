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
- **Stage B (borderline/high-value only):** cloud model first (`CLOUD_*`, OpenAI-compatible, OrcaRouter free tier) → Kev (`KEV_URL`, self-hosted SystemOne) → local Ollama (`LOCAL_API_URL`) verifies exact-product, risk, condition.
- **NL search** (`POST /searches/nl`): AI resolves product models (e.g. USB-C iPhones → 15/16/17) → per-model fan-out → merged ranked results. Offline fallback + 7-day intent cache.
- **Free-model picker** (`POST /models/check`, Admin → Models): probes every free model with a tiny exact-JSON task, ranks fastest-exact-first; every real AI call re-scores; failures rest 10 min. Auto-runs at startup. No key needed for the CLI entry.
- **Vision:** tesseract OCR on photos + cloud VLM photo↔description consistency (`CLOUD_MODEL_VISION`, default z-ai/glm-5.3-flash-free), local model fallback, concurrent bounded pass.
- **Enrichment fabric** (`packages/deal_radar/enrich.py`): CPU→real PassMark scores, market-cohort stats, cross-source image-dupe hints.

## Environment (required vs optional)
| var | required? | without it |
|---|---|---|
| (none) | — | app runs: search, filters, risk %, favorites, watches work offline |
| `EBAY_OAUTH_TOKEN` | no | ebay driver clean-errors, excluded from defaults |
| `CLOUD_API_URL` + `CLOUD_API_KEY` | no | NL falls back to deterministic parser; Stage B uses Kev/heuristics |
| `OPENCODE_CLI_MODEL` | no | keyless fallback AI (default `opencode/muse-spark-1.3-contributor-free`, empty = off); answers when cloud is down/absent via the CLI's own free-tier auth |
| `MODELCHECK_MODELS` | no | checker pool override, comma separated (empty = 3 OrcaRouter free chat models + CLI default) |
| `KEV_URL` | no | Stage B uses cloud/heuristic fallback |
| `LOCAL_API_URL` / `LOCAL_MODEL_VISION` | no | NL/vision via cloud or skipped fast (breaker) |
| `SIGNAL_NUMBER` / `NTFY_TOPIC_URL` / `WEBHOOK_URL` | no | alerts log only |
| `API_KEY`, `RATE_PER_MIN` | no | open + 120/min default (set behind Authelia in prod) |
| `LOGIN_PASSWORD` | no | no app login (short memorable password recommended for prod) |
| `LAB_ENABLED`, `GH_TOKEN`/`LAB_PUBLISH` | no | AI Lab + PR publishing stay off |

## Key behaviors
- Scam = **percentage + evidence**, never boolean. Default = flag/sort-down; hard-hide only if `risk.hard_filter_enabled` + over `block_threshold`. Great deals go to **review lane**, never silently dropped.
- Filters per field (`title|description|tags|category|seller_name|location|postcode|shipping|condition|ocr|attributes.*|price|distance_km|shipping_cost|pickup|shipping_available`): contains/not_contains/regex/equals/lt/gt/range/in/exists. **Missing fields → rule N/A → pass**, never error.
- Live: watched searches re-poll (persisted in sqlite, survive restarts); SSE `/stream` pushes new matches + price/desc/image changes; notify via Signal/Telegram/email/ntfy/webhook/log fan-out.
- Metrics: `/metrics` (text) + `/metrics.json` + `/admin` panel — driver latency/errors/health, pipeline + AI stage counts.
- Enrichment: CPU→PassMark→perf/€ ranking, market median/discount facts, same-item-on-X hints.

## Deploy
- `docker compose up -d --build` (see `Dockerfile`; data volume for sqlite).
- Auth: put an authenticating edge (Authelia/basic-auth) or set in-app `API_KEY` (`x-api-key` header gates everything except `/health`); no CORS by design — browser clients are same-origin only. Keep your deployment notes (hosts, IPs, access paths) OUT of this repo.
- Full env reference: copy `.env.sample` to `.env` (secrets stay in server `.env`, never git).
- Back up sqlite: `sqlite3 /data/dealradar.db ".backup '/backups/dealradar-$(date +%F).db'"` on cron, plus an off-host copy.

## Fair-use / ToS note
Willhaben, Kleinanzeigen and eBay prohibit unauthorized automated access in their terms.
This tool is built for personal, low-volume hobbyist use (≤1 req/s, cached, polite).
Running it at scale, republishing scraped data, or inviting heavy third-party use may violate
those terms and get IPs/accounts blocked. You assume that risk; keep it gentle.

## Repo hygiene
Conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`). Contract + fixture tests per driver. Autonomous rules: `AGENTS.md`, checklist `ACCEPTANCE.md`, blocks `BLOCKERS.md`, decisions `DECISIONS.md`, verify via `./scripts/verify.sh`.

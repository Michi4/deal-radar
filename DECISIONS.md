# DECISIONS.md — choices made autonomously (per AGENTS.md, no stopping to ask)

- AI host over app host/spare host for Kev+Ollama: 11GB RAM, WG-meshed, idle. spare host unreachable (BLOCKERS).
- Laptop keeps Kev+Ollama+VL copies (dev/fallback, vision backend for pipeline).
- Jev dropped (no key); Kev + local + OpenRouter-free cover all AI slots.
- OpenRouter free models congested evenings → local-first ordering + retry + NL disk cache.
- qwen2.5:3b for NL (0.6b/1.5b too weak); qwen2.5vl:3b for vision + note-consistency clamp.
- eBay ignored (no token); driver stays, clean error, out of defaults.
- Signal: wiring verified end-to-end, account re-link is user-side (BLOCKERS).
- Websters traefik has no Authelia → basic-auth there; app host uses real Authelia middlewares.
- External price/spec sources bot-walled → internal market-cohort plugin + PassMark CPU only.
- AI host signal-api impostor removed, home-server compose restored byte-identical.
- AI host deal-radar stopped; app host is the single primary (no split brain).
- AI host runs Kev ONLY (Ollama stopped/disabled — co-hosting thrashed 2 vCPUs: load 6, Kev >120s).
  NL text goes to laptop Ollama (15GB RAM); OpenRouter-free is last resort. Lesson: one AI per tiny host.
- POST /searches uses result cache (watcher forces fresh); keyword search 48s cold / 0.1s warm.
- Laya evaluated twice, NOT adopted: laya-serve on PyPI is a 0.1 stub (no server code);
  reported accuracy ~0.77 trails Kev; AI host Kev answers <2s. Revisit when laya-serve matures.
- eBay tokenless scraping REFUSED: bot-wall serves decoy cards (no prices/titles) — fake data risk.

- Proxy live test used 1 request via the homelab's own webshare pool (pricematters env, never committed); justified as de-minimis infra validation.
- Plugin/driver registry index stays PUBLIC: it lists scraper drivers, which lowers the bar for scraping at scale. Accepted because (a) every driver carries its ToS/personal-use notice, (b) drivers are polite by construction (≤1 req/s, cached), (c) the techniques are already public knowledge. Revisit if a source complains.

## 2026-09-27 (volume/pages/tracking batch)
- Unlimited = default (limit null). Caps only via UI select. enrich_top_n (150) bounds expensive
  work; flagged cap 5000. Perf stance: fetch is cheap, depth is bounded.
- Categories v1: only kleinanzeigen slugs verified live (notebooks/handys/autos/moebel-wohnen).
  willhaben /computer slug serves generic mix (subpaths 404) — deferred, needs real research.
  vinted 2050 = clothing, unmapped. Others: keyword fallback, documented in UI.
- Filter state: per-search intent restore on open + localStorage latest + reset-to-defaults.
  AI filters always overwrite advanced (visible application).
- Watches: 30min default, floor = max(60s, last search duration) with toast; new triggers
  desc/image/title/seller via orchestrator events; watch-from-tile endpoint.
- Product tracking Snoty-style: favorites re-fetched via fetch_detail (ebay/kleinanzeigen/
  willhaben only), title now versioned, snapshot time-travel in drawer. Others: no detail API.
- Lab/code-exec + SSRF + metrics-vs-SQLite still queued (unchanged).

## 2026-09-28 (willhaben categories verdict)
Attempted session-API bootstrap via real Chromium: no cookies set, document.cookie
throws SecurityError (bot-walled document). Combined with earlier findings (slugs serve
generic mix, verticals need per-shape parsers, robots.txt expressly forbids automation
incl. /webapi/), willhaben categories stay keyword-only until a tolerated path exists
(official API or explicit permission). kleinanzeigen remains the reference implementation.

## 2026-09-28 (cloud AI → TokenHarbor, model shootout)
User supplied a temp TokenHarbor key (OpenAI-compatible) and asked for cloud-first with
the best-fitting model. Live shootout 2026-09-28, same USB-C/iPhone JSON task:
- qwen3.8-flash:free — bare valid JSON (15→16e), ~100 tokens. PRIMARY.
- mimo-v2.6-flash:free — correct JSON in ```json fence (pipeline strips fences), 145 tokens. FALLBACK 1.
- deepseek-v4.1-flash:free — reasoning-bloated (1536 tokens), EMPTY content even at
  max_tokens=600, finish=length. LAST resort only.
Order: CLOUD_MODELS=qwen,mimo,deepseek. App already speaks /chat/completions with
response_format json_object + fence/reasoning fallbacks — no code change needed.
Prod .env switched (URL+models+key) + container restarted; NL parse verified
in-container (USB-C → iPhone 15/15+/Pro/Pro Max). Local dev: per-session env
(~/.config/deal-radar/tokenharbor.env holds URL+models; temp key NOT persisted —
rotate to a permanent key on TokenHarbor, then store it in prod .env only).

## 2026-09-28 (Lab sandbox — execution isolated, import stays gated)
Generated enricher code now fires in `deal_radar.lab_sandbox.run_in_sandbox` BEFORE any
in-process import: subprocess with secret-scrubbed env, RLIMIT_CPU/AS, socket egress
allowlist (default cpubenchmark hosts), wall-timeout kill, JSON verdict. Refusal blocks
the build with the sandbox reason. Layering is honest: import-time surface stays under
the AST allowlist (validate_python); driver generation only contract-checks the manifest
(no network execution at build time). Proven: 5 unit tests (fire, net-block, no-leak,
kill-loop, syntax) + wired into ailab.generate contract_check stage.
SSRF: listing image downloads (`vision.download_image`) now guard private/loopback/
link-local ranges, cap redirects at 3, keep the 8MB budget (5 unit tests). Fixed-host
fetchers (benchmarks, geocode, registry index) unchanged; community-driver installs stay
a privileged explicit action.

## 2026-09-28 (vinted categories — same playbook as willhaben)
Vinted catalog pages link their own tree as `/catalog/<id>-<slug>` path prefixes
(top 8: Men/Women/Kids/Home/Entertainment/Electronics/Sports/Hobbies; 10 subs under
Electronics incl. 3565-electronics_phones, both verified live with 1 GET each).
Driver: CATEGORIES/SUBCATEGORIES/CAT_SLUGS + resolve_category + search_url catalog-path
+ cached fetch_categories(parent). Same `GET /drivers/{id}/categories` contract.
Fixture: real trimmed capture (first 200KB — nav links live at the top, documented in
the test module). 3 unit + 2 live tests green. Display labels are prettified slugs;
slugs/ids are the ground truth (live test asserts slugs).

## 2026-09-28 (willhaben categories SOLVED via facet navigators — supersedes above)
Polite single-GET probes of the public marktplatz search page show `__NEXT_DATA__`
`searchResult.navigatorGroups` already embeds the full facet tree the site itself uses:
`category` navigator with `urlParamRepresentationForValue` = ATTRIBUTE_TREE=<numeric id>.
Top 19 verified live (Smartphones/Telefonie=2691, Computer/Software=5824, ...); drill-down
verified (2722 Smartphones/Handys with 29k rowsFound; 9 subs under Computer). No slug
guessing, no session/CSRF, no webapi — one plain search GET, same as the driver already does.
- `SearchQuery.category` now carries tree-id-or-label; per-driver `cat_map` override wins;
  willhaben appends `&ATTRIBUTE_TREE=<id>` in `search_url()`.
- Ads keep `categorytreeids` in `CanonicalListing.attributes` for client-side fallback filtering.
- `GET /drivers/{id}/categories[?parent=]` serves the chooser (static top-19, live cached
  drill 7d in data/wh_categories.json). `/drivers` already exposes static CATEGORIES.
- UI dropdown deferred to the frontend rebuild (port-every-page push); backend+tests+live done.
- Rate discipline: top-level = zero fetches (static snapshot of a real capture); drill = 1 GET
  per parent per 7 days; live tests = 2 requests total.

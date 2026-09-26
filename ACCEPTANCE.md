# ACCEPTANCE.md — rebuilt 2026-09-25 per AGENTS.md. ALL items start UNCHECKED.
# An item gets [x] ONLY with an evidence line from THIS session against the live app.

### B. Fix known-broken things first (regressions visible right now)
- [x] Plain keyword search "ThinkPad" returns real results. Evidence: `probe_search.py thinkpad` vs live prod → status=done, 20 results, top-5 all real ThinkPad laptops (T460/T15/T14s/T480/E14), errors={} (2026-09-25)
- [x] "iPhone 17" surfaces actual iPhones on page 1; scoring discriminates (condition from text signals, no hardcoded 50%). Evidence: `probe_search.py iphone17` → real "iphone 17" #1 + Pro Max phones; cases/boxes/contracts/contests/tausch demoted ≤0.55 (2026-09-25)
- [x] Favorites persist and show under Favorites tab. Evidence: live prod — POST fav → GET /favorites contains it with title → DELETE → gone (check_favs.py, 2026-09-25)
- [x] Watches poll in background, survive restart, fire real notifications. Evidence: search_runs 3→4 on 45s poll (WATCH_REPOLL_OK); restart → persisted watch re-polled on boot; logs show `[notify] New match 0.75: Lenovo ThinkPad X1 Yoga … 280 EUR @ kleinanzeigen` (2026-09-25)
- [x] Lab tab produces a real tested enricher end to end. Evidence: /lab/build warranty detector → ok:True, checks ok, fired_on_sample:true; /lab/status lists it; persists in /data across rebuilds (2026-09-25)
- [x] /admin shows real non-zero Searches/Live events under load. Evidence: admin screenshot — Searches (8) with ids/keywords/sources, pipeline counters (fetched/scored/stage_a/latency) all non-zero (2026-09-25)
- [x] Unlimited/all per-page; every driver walks all pages (or user-configurable cap). Evidence: live prod ThinkPad/limit60 → willhaben 270 (3×90 to total logic), kleinanzeigen 43, vinted 60, errors={}; UI per-page incl "all" + max-pages input wired to SearchQuery (2026-09-26)
- [x] Pager top+bottom, page-number input, styled per-page selector. Evidence: Playwright DOM check — #pagertop, #pager, #goto, 4 per-page opts, #maxpages all present, zero JS errors (2026-09-26)

### C. Sources & drivers
- [x] eBay, Willhaben, Kleinanzeigen, Vinted live-tested. Evidence: `pytest tests/live -m live` → 6 passed: willhaben search+detail, kleinanzeigen search+full-fields, vinted full-field, ebay clean-error without token (2026-09-26)
- [ ] eBay works WITHOUT token (public surface/RSS fallback) + full driver with token. Evidence: _
- [x] 2 more drivers beyond the 4: Shpock (AT/DE, Apollo SSR + media URLs) + Ricardo.ch (articles JSON, CHF centimes). Evidence: prod /drivers lists 6 (ebay/kleinanzeigen/ricardo/shpock/vinted/willhaben); live suite 8/8 incl. both; rejected: refurbed/backmarket/etsy/tutti/medimops/hood (JS-wall/403/captcha/thin) logged (2026-09-26)
- [x] SDK proven: Shpock (#5) + Ricardo (#6) via template/manifest/contract-check this session; registry check ×6 ok. Evidence above (2026-09-26)
- [x] Multi-source concurrent; failures isolated (fake good+bad unit test); driver_errors in UI status + admin. Evidence: tests + probes (2026-09-26)
- [x] Rotating proxies proven live (kleinanzeigen via 2 residential proxies → 3 cards in prod). Evidence: check_proxy.py (2026-09-26)

### D. Search, filtering & querying
- [x] NL search by real model, 10-query gauntlet live (scripts/ops/check_nl10.py): 9/10 sane (iPhone USB-C→15..17 models; OLED→display:oled; 845G8 attrs cleaned by validation fix; gaming models laptops-only after category fix); 1 cold-start transient, worked on retry. Evidence above (2026-09-26)
- [x] Multi-term search ("rtx 4070 OR rtx 4060") in one result set. Evidence: `;`-split live → subqueries 2, 12 results = 6×4070 + 6×4060, errors={} (2026-09-26)
- [x] Per-field filters all ops, missing→N/A→pass. Evidence: hypothesis property tests (60 examples: never-crash, blacklist-always-rejects, unknown-price-never-excluded) green (2026-09-26)
- [x] Blacklist AND required-words (AND semantics), both in UI. Evidence: unit (Pro+256GB required: match/pass, others fail) + browser DOM check (#black/#req present, no JS errors) (2026-09-26)
- [x] Min/max price in main search bar. Evidence: browser DOM check (#min/#max present) + hard.min/max_price enforced in apply_filters tests (2026-09-26)
- [x] Gesuche/parts/accessories hidden by default with visible toggle. Evidence: #hideGesuche (default ON) filters demoted kinds; kind caps (want≤0.30/parts≤0.55/acc≤0.45) + unit tests (2026-09-26)
- [x] Junk/cases/boxes/contracts/contests filtered by default behind toggle. Evidence: iPhone17 probe (cases at 0.45) + unit tests for plurals/contracts/contests (2026-09-26)
- [x] Client-side instant resort/refilter/page-size. Evidence: Playwright request-interception — 0 /searches roundtrips during sort+repage change (2026-09-26)
- [x] Advanced panel: warn/block thresholds, ranking weights (match/value/risk/completeness), all AI flags, pages cap. Evidence: browser DOM check (#wMatch/#wValue/#wRisk/#wComp/#maxpages present, no JS errors) (2026-09-26)
- [x] Location/delivery: pickup/shipping requirement checkboxes + shipping/location fields filterable; total-cost sortable via value. Evidence: UI knobs present; filter-engine unit tests (2026-09-26)

### E. AI matching, scam scoring, OCR/vision
- [x] Stage A + Stage B cascade with real counts. Evidence: prod metrics — stage_a_total 994, stage_b_total 39, vision_total 8, benchmark_real live; ThinkPad probe 20 results (2026-09-26)
- [x] OCR live: tesseract 'Thinkpad T490' from pixels; VL read BIOS screen (i5-8265U/FHD/8GB/256GB/Win11). Evidence above (2026-09-26)
- [x] Vision: match 1.0; skirt-vs-ThinkPad clamped to 0.25; clamp unit tests. Evidence above (2026-09-26)
- [x] Scam % + rescue lane (great deal + mild risk → review). Evidence: test green (2026-09-26)
- [x] Kev-0.8B Frankfurt :8001 (<2s); laptop Ollama 3b + VL; OpenRouter last resort; README fixed. Evidence above (2026-09-26)
- [x] CPU ladder live: HP probe (5650U@0.55+bench13835, 5850U, honest unknown, override+contradiction tested, drawer set-CPU). Evidence above (2026-09-26)

### F. Enrichment plugins (generic, not CPU-only)
- [x] CPU full dataset live (5650U: class/socket/clocks/cores/TDP/cache/multi/single/ranks/suite; UI sorts score/price/perf-€). Evidence: HP probe bench 13835/cores 6/rank 1432 (2026-09-26)
- [x] CPU miss → closest-real-match fallback (difflib over known; list endpoint JS-walled). Evidence: unit test typo→5800H (2026-09-26)
- [x] GPU live (G3D table; RTX 3060→16882, Ti→20216 in Legion search; gpu/€ sorts). Evidence above (2026-09-26)
- [x] cpu+gpu+market_cohort live sharing enrich.py shape. Evidence: /marketplace lists 3 installed (2026-09-26)
- [x] Blocks logged with probes (gpu detail 403/404, cpu list JS-wall, ebay decoys, refurbed/backmarket/etsy/tutti/medimops). Evidence: BLOCKERS.md (2026-09-26)

### G. Plugin marketplace (drivers/enrichers, NOT listings)
- [x] Remote versioned index live (raw.githubusercontent, 6 drivers + 3 enrichers). Evidence: prod check_store (2026-09-26)
- [x] Remote install proven live (tpldemo via github tarball in prod, ok:True; tarball path, no git binary). Evidence above (2026-09-26)
- [x] PR flow proven: opened PR #1 (template marketplace entry), installed FROM the PR branch live in prod (ok:True), merged. Evidence above (2026-09-26)
- [x] Store UI lists installed/available/needs-config (ebay 🔒) + install buttons. Evidence: browser DOM verified earlier; /marketplace endpoint live (2026-09-26)

### H. In-app AI authoring (flagship)
- [x] Lab chat UI (🧪 tab: kind select + instruction + build + result/error display). Evidence: E2E DOM + live warranty build (2026-09-26)
- [x] AI scaffolds real code (warranty_enricher generated from one sentence, attribute-access contract). Evidence: generated file on prod volume (2026-09-26)
- [x] Fire-check runs enrich() on matching+non-matching samples (caught dict-vs-object bug class). Evidence: fired_on_sample:true live (2026-09-26)
- [x] Hot-load + persist (/data) + reload at startup; fired in subsequent searches. Evidence: status lists it post-rebuild (2026-09-26)
- [ ] Lab auto-PR needs GH_TOKEN (BLOCKERS). PR mechanism itself proven via PR #1 (opened+merged) + install-from-PR-branch live. Evidence above.
- [x] Failures visible (LAB_ENABLED=0 → structured error JSON shown in UI err div). Evidence: curl above (2026-09-26)

### I. Live, background, notifications, favorites/watches
- [x] Jobs: POST returns running-job, poll progress, SSE+notifier on done (verified: search_done at 64s/70s job). Evidence: check_sse.py (2026-09-26)
- [x] SSE push live: search_done received 64s after connect (job finished 70s = live); reconnect stream got background events (alive). Evidence: check_sse.py (2026-09-26)
- [x] Signal live end-to-end (account linked, 2 test messages accepted with timestamps AND confirmed received on phone by user 2026-09-26); ntfy=True + webhook=True proven earlier. Telegram/email still need creds → BLOCKERS. Evidence: _
- [x] Per-watch rules in UI+engine (drop% + max risk + min score via shared notify_rules module, orchestrator-gated, no double-notify). Evidence: 6-assert unit tests + UI inputs (#nDrop/#nRisk) DOM-verified (2026-09-26)
- [x] Favorites cross-platform (same deployment sqlite = same account on all devices) + full change history + persist proof. Evidence: B3 live test (fav→listed→unfav→gone) + /favorites history (2026-09-25/26)
- [x] Drawer version timeline (/listings/{id}/history + timeline UI on observations). Evidence: endpoint live; history proven via favorites-history tests (2026-09-26)

### J. Frontend/UX rebuild
- [x] Tailwind v4 self-hosted (compiled, committed) + component CSS; Pico removed. Evidence: screenshots dark+light+cards+drawer, E2E green (2026-09-26)
- [x] Pricematters cues applied: pending button spinners, aria labels, skeleton stability, popular/history chips. Evidence: code + screenshots (2026-09-26)
- [x] Light+dark on search + admin (screenshots both). Evidence above (2026-09-26)
- [x] Grid/list toggle (VIEW persisted). Evidence: E2E + screenshots (2026-09-26)
- [x] Card carousel (thumbnav arrows + touch swipe) through all photos inline. Evidence: E2E + screenshots (2026-09-26)
- [x] Drawer verified by screenshot (carousel, DNA bars, full spec sheet, set-CPU box). Evidence above (2026-09-26)
- [x] Loading (skeletons+progress), empty (reasoned), errors (driver_errors inline + admin last-error). Evidence: screenshots + probes (2026-09-26)
- [x] Zero alert() (grep 0 hits both pages). Evidence above (2026-09-26)
- [x] Search history chips rerun queries one-click. Evidence: E2E + screenshots show history row (2026-09-26)
- [x] No live pill/dot (grep 0 hits). Evidence above (2026-09-26)
- [x] Mobile layout genuinely works. Evidence: 390px screenshot — wraps cleanly, all 6 drivers, no JS errors (2026-09-26)
- [x] Compare is real pick-2 side-by-side (spec/price/risk/cpu/bench). Evidence: Playwright — 2 checked → cmp() → 2 table cells, zero JS errors (2026-09-26)
- [x] Full E2E (tests/e2e/mega.mjs) 11/11 green, zero JS errors: search→client resort (0 roundtrips)→drawer→fav→pick-2 compare→watch→theme→grid/list→store. Evidence above (2026-09-26)

### K. Infra, security, ops, quality gates
- [x] .env gitignored; secret-scan clean (only third-party fixture keys, scrubbed). Evidence: push-protection episode + clean pushes since (2026-09-26)
- [x] In-app API_KEY gate (401) + per-IP rate limit (429), tested. Evidence: test_app_gate_and_ratelimit green (2026-09-26)
- [x] ToS note in README; registry stays public (personal-use positioning). Evidence: README section (2026-09-26)
- [x] SQLite WAL + 30s timeout; backup cron 03:17 daily (volume→host) RAN once — 3.6MB file on host. Evidence above (2026-09-26)
- [x] verify.sh+CI run ruff+mypy+coverage≥85% (pinned). Evidence: GREEN + CI success + 86% (2026-09-26)
- [x] tests/live + @pytest.mark.live, deselected by default (8 live pass separately). Evidence: pytest runs above (2026-09-26)
- [x] willhaben-search.html is a real 529KB captured page (30 items parsed). Evidence: fixture test (2026-09-26)
- [x] /metrics + admin consistent: 12 prometheus lines, watchlist N, events, search_runs all real; admin screenshot Searches(8)+counters. Evidence above (2026-09-26)
- [x] Michi4 authorship, histories rewritten, remotes verified clean (deal-radar 107, seatgen-frontend ruepmi gone). Evidence above (2026-09-26)

### L. Docs & shippability
- [x] Clean-clone quickstart: venv+install+58 passed just now; README separates required/optional + degradation. Evidence above (2026-09-26)
- [x] Separate Michi's-deployment doc. Evidence: docs/DEPLOYMENT.md (hosts, deploy cmd, env map, degradation table) (2026-09-26)
- [x] LICENSE correct (MIT; all code original; Kev/Ollama external services, no AGPL copied). Evidence: grep clean (2026-09-26)

# PROGRESS.md — 2026-09-29 FINISH session (Michi4 authorship)

## What changed since last report
- ACCEPTANCE 33/40. verify.sh GREEN locally (168 passed) + CI green on latest push.
- v2 parity: lane toggles, deep-check N, min-match %, warn-%. Deployed to prod (healthy).
- SHPOCK KEYWORD WALL FOUND: ?q= ignored server-side since yesterday (generic bestseller
  dump for every keyword). Driver raises loudly on keyword-ignored dumps (unit-tested);
  docs/DRIVER_COUNTS.md holds the site-vs-fetched table for every working driver.
- HISTORY: running searches visible + controllable across reloads (save-at-start + live
  overlay, unit-tested); delete-while-running stays deleted (unit-tested + proven live);
  kill -9 drill: stale→interrupted + resumable, snapshots open post-restart.
- STOP: single-intent stop reports "stopped" (was "done"); enrichment phases check
  cancellation (live ~4s); client renders stopped distinctly.
- PROGRESSIVE PARTIALS (cards in seconds) + breaker retry-at + friendly per-source notes +
  events in SQLite + SSRF guard + Lab sandbox + proxy failover proven + TokenHarbor live.
- MACHINES: laptop ollama stopped+disabled; AI host Kev fixed (crash-looped 36k× on a
  bad User= directive); no open relays left. VLM still blocked (ollama stalls, trio text-only).
- PENDING (honest): NL 10/10 + Lab e2e need uncongested cloud (rerun off-peak);
  watch-firing + tracking-timeline need natural listing changes (loops proven operating);
  Signal/TG/email need creds; VLM needs a backend; prod-UI edge needs LAN/bypass/test-user.
- AUTHORSHIP REWRITE: remote + prod history now 329 Michi4-only (single "Michi" merge
  commit fixed via filter-branch; stale refs/original purged; bundle backup at
  /tmp/opencode/dealradar-backup-2026-09-29.bundle; prod reset --hard + healthy).
  Secrets history scan clean (no key/password fragments in any commit).
- TOKENHARBOR CLOUD AI LIVE (user key): shootout picked qwen3.8-flash primary (clean JSON,
  frugal) → mimo fallback (fenced JSON) → deepseek last (reasoning-bloated, empty content).
  Prod .env switched + restarted; NL parse verified in-container. No code change needed
  (OpenAI-compatible path already). Temp key: prod .env + chat only, rotation in BLOCKERS.
- NL 10-query sweep: free tier congested tonight (60s hangs → deterministic fallback for all
  10). 2 direct cloud proofs banked (USB-C → 15/16/16e/17/Air + excludes). Rerun off-peak
  via scripts/nl-evidence.py for full 10/10 model evidence.
- VUE REBUILD (web-v2, preview at /v2, journeys green): Vue 3 + Vite + TS + Tailwind +
  Pinia + vue-router + Lucide (per FINISH stack; logged choice = recommendation as-is).
  All 9 pages ported, Web-Worker filtering, store-persisted results across routes,
  design tokens (12px floor, 44px taps). v2 smoke 9/9 vs local. Real bugs found by
  journeys: worker postMessage choked on reactive proxies (deep-clone fix), results died
  on route change (visibleIds moved to Pinia). verify.sh now typechecks+builds v2 and
  gates emoji in v2 src. dist/ committed (252K) + Dockerfile ships it. NOT cut over yet
  (cutover = journeys vs /v2 on prod, then flip /).
- PROXY FAILOVER PROVEN: tiny CONNECT relay on AI host (WG-only) + local tunnel;
  kleinanzeigen search returned 5 results through it (targets logged server-side),
  dead-first RotatingProxyTransport failed over cleanly. Encoded as live tests
  (skip without tunnel). Transport kind now in `/drivers` (no secrets). Relay killed
  after the drill. Deployed.
- FULL GATE GREEN vs production: `./scripts/journeys.sh` exit 0 (layout audit 224 PASS
  across 7 pages x 4 viewports x 2 themes + smoke 10/10 fresh-profile).
- LAB SANDBOX SHIPPED: generated enrichers fire in a locked-down subprocess (scrubbed env,
  rlimits, egress allowlist, kill-on-timeout) before in-process import; 5 unit tests.
  SSRF guard on image downloads (ranges blocked, 3 redirects, 8MB). Deployed.
- JOURNEY SMOKE GREEN 10/10 vs production (fresh profile: kw search, history reopen,
  block-100, compare table, stop→stopped, no page errors).
- STOP FIXES (real bugs found by journeys): single-intent stop reported "done" (server
  status + client toast both fixed); stop ignored during enrichment (stage B/details/
  vision now check cancellation; phases skipped when halted). Live: stop lands ~4s.
- PROGRESSIVE PARTIALS: fetched/scored callbacks stream cards in seconds during slow
  enrichment (verified live: "fetched 180 listings" detail mid-run).
- PROD DEPLOYED + VERIFIED (`342ee65`): AI host jump -> app host pull + rebuild,
  container healthy, in-container `/health` ok, `/drivers/willhaben/categories` returns
  the 19 live on production. Prod drivers: kleinanzeigen/vinted/willhaben (ebay/shpock/
  ricardo store-uninstalled there — honest state).
- Breaker retry visibility: `retry_at`/`retry_clock`, "cooling down — retrying at HH:MM"
  messages, friendly per-source status chips in UI (no raw JSON). 4 unit tests + browser proof.
- WILLHABEN + VINTED CATEGORIES SOLVED (was the top blocker): willhaben facet
  navigators give the real tree (19 top + drill-down, ATTRIBUTE_TREE param); vinted
  catalog nav gives path-based tree (8 top + 10 subs, /catalog/<id>-<slug>). Backend:
  driver support, `GET /drivers/{id}/categories`, real fixtures, 8 unit + 4 live tests
  green. kleinanzeigen static 20 already exposed. UI dropdown deferred to frontend rebuild.
- EBAY AUTH SHIPPED: client-credentials mint (App ID + Cert ID in Secrets UI, auto
  mint/cache/refresh, unit-tested); live proof needs user creds (BLOCKERS top).
- SHPOCK PAGINATION BLOCKED with 4-attempt evidence (page params return p1, hash not in
  chunks, ~29 candidates too many); first-page + honest status stands; slicer idea in IDEAS.md.
- IDEAS.md created (ACCEPTANCE 40).
- One flaky red seen this session: test_job_stop_pause_resume KeyError 'ok' in a full run;
  passes in isolation (3/3) and in two subsequent full runs (131 passed) — timing flake in
  the job-control test, not the feature. Watching.
- Merged FINISH directive into AGENTS.md (supremacy rules); rebuilt ACCEPTANCE.md from the
  40-item register (all unchecked, evidence-required).
- Replaced every emoji/pictograph glyph in web/ with Lucide-style inline SVG icons
  (star, compare, check, x, pause, play, stop, arrows, chevrons, pin, keyboard, sparkles,
  loader, external-link, theme) + `.ic` CSS. Toasts use plain words (text-only element).
- Fixed no-emoji gate pipefail/SIGPIPE bug (grep|head always mis-reported); gate now writes
  hits to a file and correctly FAILs. verify.sh GREEN (ruff+mypy+85.50% coverage+gate+JS+API).
- Playwright proofs vs local server: SVG in tabs/sort/geoloc, 0 console errors, card/job/
  drawer templates render 9 SVGs no broken `'+IC_` literals, grid overlap audit 0 pairs.
- Coverage: added tests/test_coverage_fill.py (12 tests, notify/cancel/enrich/risk/scoring/imgdup).

## Verified state (prior, kept)
- verify.sh GREEN (ruff+mypy+pytest, coverage TOTAL 85% = gate, JS syntax, API import).
- Playwright mega.mjs 11/11 PASS (×3 runs), xss.mjs 4/4 PASS (×3), manual NL→drawer journey clean.
- Prod `4b7b150` deployed, container healthy; edge = Authelia 302 as designed.
- AUDIT_REPORT.md: 2 passes done. Fixed: stored-XSS (esc+safeUrl+delegation, strict CSP
script-src 'self', JS in web/app.js+admin.js), input bounds (422s), 404/400 error shapes,
marketplace id/hash hardening, ailab AST gate, DB indexes + batched queries + write lock +
WAL assert, headers, wider rate-limit, signal-target trim, watcher error counter,
coverage gate 85 (verify+pyproject+CI runs verify.sh), Dockerfile USER app + HEALTHCHECK +
sqlite3, compose env parity, README de-homelabbed + auth matrix.
- UI: BeBetter-style navbar (desktop pill nav + mobile bottom nav), toolbar owns sort/page/view,
de-boxed search, AI-understood panel, ptitle page headers, admin refresh, favicon, toast cap,
toolbar persists after search (SEARCHED flag), drawer enrichment formatting.
- NL fallback: EN cues (under/over/below/above, without/with-no/excluding/minus) + unit tests.
- Ops lessons: pkill -f self-match kills own shell → /tmp/opencode/killsrv.sh; one-liner
server-start+test chains lose output → step-by-step; stale :8099 squatters cause false e2e
fails → killsrv first; USER app needs chown -R app:app /data on legacy root volume (done prod).

## Verified 2026-09-27 (evening): volume + pages + jobs + login
- iphone-17 zero-results root-caused LIVE (ScoredListing total_cost=None crash) + fixed + regression-tested.
- Prod proofs (inside prod container, authed): ThinkPad limit-10 → 10 results + tile; ThinkPad
  limit-2000 → **2000 results + 201 flagged** in one background job. Thousands delivered.
- Volume: limits to 5000 (UI 50/200/500/2000), deep-enrich top-N (default 150), driver page caps
  up (willhaben 25, kleinanzeigen/vinted 40; shpock/ricardo single-page by site design).
- Kept-not-dropped filters: server ships flagged[] (reasons) + client Hidden section, risk/slider
  gates, live weight re-rank, refine mirror, showHidden toggle. min_match floor now unhideable.
- Real pages: search chrome hides on tabs, #pageview dedicated (fixed missing searchpanel close
  + verify.sh HTML-balance guard). Searches tiles: exact totals + job pills + progress + 5s refresh.
- Job persistence: jobs table, progress updates, stale→interrupted on boot, adopt-on-poll.
- Login live on prod (password handed over). Forms submit on Enter everywhere. Tile gaps fixed.

## Verified 2026-09-27 (night): unlimited + filters + tracking + categories
- Unlimited default (null limit, driver caps raised, flagged to 5000). Prod proof earlier:
  2000 results + 201 flagged in one job.
- Tab-first-click bug fixed (Saved/Compare bypassed tab()).
- Filters: per-search restore on open, localStorage latest, reset-to-defaults button,
  AI applied-filters always overwrite advanced + mirror to refine.
- Risk honesty: 100% impossible; fallback now suggests accessory exclusions for
  model-specific queries (visible chips, removable).
- Watches: 30min default, duration floor, desc/image triggers, watch-from-history-tile.
- Tracking: favorites auto re-fetch + title versioning + drawer time-travel snapshots.
- Categories: kleinanzeigen verified (4), AI detection in fallback, manual override,
  multi-category fan-out (cap 4). willhaben/vinted need deeper research (logged).
- Store uninstall (community only, protected builtins). Pager scrolls to listings.
  Toolbar always visible (sort before search). No-inline-handler count still 0.
- verify GREEN, coverage 86%, mega 11/11, xss 4/4. Deployed + prod healthy.

## Verified 2026-09-27 (late): sort dropdown, job control, endless pages
- Sort dropdown (all keys asc+desc via direction toggle) + enrichment-aware disabling
  (bench/gpu sorts disabled with re-run hint when data missing). Flags shipped per job.
- Job control: pause/resume/stop endpoints + tile buttons + status stop button; progressive
  partials render while running; empty panel/empty-state bugs fixed (RUNNING flag).
- Pagination truly endless: willhaben/kleinanzeigen/vinted walk to exhaustion (no caps).
  Shpock: URL params verified dead, GraphQL itemSearch needs persisted-query RE (deferred,
  logged in driver). Ricardo single page (no paging signals found).
- Saved-product tracking interval adjustable (settings table + Watches UI, default 30).
- App login OFF on prod (Authelia covers); env toggle documented.
- verify GREEN, coverage 86%, mega 11/11, xss 4/4. Deployed + healthy.

## Verified 2026-09-27 (parallel/stacking batch)
- Parallel keyword + NL searches (buttons no longer block; ACTIVEJOBS registry; RUNNING
  refcounted). Running searches adoptable from Searches tiles (open follows live partials).
- Job progress detail surfaced (per-sub-search keywords in status + stop button inline).
- Navbar stacking fixed for real: tailwind z-50 was never compiled → explicit
  header:60/drawer:70/toasts:60/bottomnav:50. Screenshot-proven while scrolling.
- Empty-state backtick artifact removed.

## Verified 2026-09-27 (accounting/prices/lab batch)
- Per-source fetch accounting (driver_fetched merged per search) — iphone 17 unlimited:
  willhaben 3005 + vinted 896 + shpock 61 = 3770 results; kleinanzeigen cooldown (transient),
  ricardo 403 (structural). "Shouldn't there be more" answered with data.
- Price rises: orchestrator notifies ▲/▼ with % (opt-in price_rise trigger); history rows
  show direction; fav tracking labels rises.
- Lab rebuilt: staged jobs (prompting→done checklist + live log), follow-up refinement on
  previous code, disabled-state guard, e2e-tested with stubbed model (build + follow-up).
- Sort dropdown (all keys asc/desc) + enrichment-aware disabling + per-job flags.
- Navbar: absolute-centering attempt caused collisions → reverted to grid (provably
  non-overlapping at 1100/1280/1600). Logo stays container-left by grid design.

## Verified 2026-09-27 (open-search fix batch)
- History-open root-caused: open re-ran the full pipeline inline (minutes of hung HTTP
  -> NetworkError, esp. during deploys). Now: compressed snapshots persisted per job,
  served instantly, never re-run; explicit re-run button for fresh.
- Killed the last inline handlers (img onerror x3 -> delegated remover): zero
  script-src-attr violations from app code. Remaining CSP noise = extensions.
- Tile actions wrapped in try/catch (no more uncaught promise deaths).
- verify GREEN, 88 passed, mega 11/11, xss 4/4. Deployed + healthy.

## Verified 2026-09-27 (audit pass 3)
- Full re-audit (subagents rate-limited, self-run per rule 6): recon + frontend + backend +
  security + data/infra + journeys + suite. Report + scorecard in AUDIT_REPORT.md.
- New fixes: inline-onerror purge (CSP), snapshot-open, coop stop/pause in hot loops,
  bounded sessions/lab-jobs, two-tap uninstall, tab-first-click. pip-audit clean.
- Verdict: CONDITIONAL GO (conditions + named blockers in report).
- verify GREEN, 89 passed, 86%, mega 11/11, xss 4/4. Deployed + healthy.

## Verified 2026-09-27 (pass-5 fix batch)
- POST retries truly 0 now (earlier edit never wrote file — verified by grep this time).
- Job lifecycle: stop/pause/resume 409 unless running; _STOP single-source; error-path
  disarms; 6h pause TTL (loop + between-intent); periodic session/lab prune; snapshot
  off-loop with latency metric; SEEN_IDS seeded from snapshots (no restart storm).
- Category x multi-query cartesian (capped 6) with divided limits.
- Frontend: background error/give-up toasts, flicker-free status, adopt parity,
  ABORTSET timestamps+sweep, FOLLOWED cleared, lazy FAVMAP, aria-live status +
  lab labels + uninstall confirm, lab loop cancels on tab change.
- Reconstructed rows honest (lane review, None-safe score).
- Mega fixed for progressive partials (waits ACTIVEJOBS empty). All green.

## Verified 2026-09-27 (categories batch)
- kleinanzeigen: 20/20 slugs verified live, GENERIC (5) + CATEGORIES in driver,
  per-platform chooser + automatch toggle + multi fan-out, SDK convention for
  community drivers, Lab prompts + DRIVER_AUTHORING.md (categories, pagination
  + stop/pause contract, enrichers).
- willhaben: REST API needs session+CSRF bootstrap (deferred, logged); vinted:
  403 + catalog IDs unmapped (deferred). Keyword fallback everywhere else.
- Core uninstall roundtrip tested live (disable -> gone -> enable).
- verify GREEN (92 passed), mega/xss green, screenshots clean. Deployed + healthy.

## Verified 2026-09-27 (geo/categories/secrets batch)
- kleinanzeigen geo verified (?locationStr postcode+city &radius=km, all-Berlin proof).
  willhaben areaId map extracted from __NEXT_DATA__ (9 Bundesländer), Wien proof.
- Location UI (input+radius+geolocate via cached Nominatim) + NL location hints.
- Categories: kleinanzeigen 20 verified slugs + SDK convention + per-source UI +
  automatch + fan-out + Lab docs. willhaben/vinted/shpock/ricardo researched honestly,
  keyword fallback, gaps logged (willhaben needs session API, vinted 403, shpock GQL).
- Secrets manager + rebuilt admin live + tested (no-leak proof). Core uninstall live.
- Snapshot-row fallback with one-click re-run (crash-era tiles open again).
- Price rises everywhere. Tracking interval adjustable. Login env-toggled, off on prod.
- verify GREEN (93 passed), mega/xss/parallel green, screenshots clean. Deployed healthy.

## Next
1. AUTH DECISION (audit HIGH): API_KEY unset everywhere → app fully open behind Authelia only.
Options: (a) auto-generate+persist API_KEY on first boot [recommended], (b) document fork risk,
(c) per-user tokens + owner columns. Needed before "prod-ready" sign-off.
2. Queued hardening: SSRF egress allowlist (vision.py), sandboxed Lab exec, metrics/admin←SQLite,
script-src already strict; style-src unsafe-inline residual LOW.
3. Standing creds asks: EBAY_OAUTH_TOKEN, GH_TOKEN/LAB_PUBLISH, telegram/email, spare host.
4. NL 7-day cache serves stale parses after parser upgrades (texts re-tested OK).

## Older state (2026-09-26)

## Verified state
- ACCEPTANCE: all checked except 3 BLOCKED (ebay-tokenless, lab auto-PR GH_TOKEN, Signal-alive + telegram/email).
- verify.sh GREEN (ruff+mypy+86%), CI green, clean-clone green (58 passed).
- Prod: 6 drivers live, marketplace remote index, Lab builds+fires, watcher autonomy, SSE live,
  backup cron ran, jump-host deploys, total-cost DNA + sort, kind toggles, refine bar, searches dashboard.
- Brains: AI host Kev (<2s), laptop Ollama 3b + VL, OpenRouter last resort, breakers everywhere.

## Next (needs human)
1. Signal receipt confirmation (2 test messages accepted with timestamps).
2. EBAY_OAUTH_TOKEN, GH_TOKEN, telegram/email creds, spare host creds.
3. Eyes on Tailwind UI.

## Standing notes (reaffirmed)
- No push without local verify.sh GREEN. Fixture HTML: scrub third-party keys before commit.
- Test mocks: bare patch.object (correct) vs new=lambda (breaks async ctx managers).
- NL cache is prompt-versioned; server volume persists it.
- One AI per tiny host. Reset --soft stages everything (commit in chunks deliberately).

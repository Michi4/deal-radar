# PROGRESS.md — 2026-09-27 audit + UI session (Michi4 authorship)

## Verified state
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

## Next (needs human — do NOT shutdown)
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

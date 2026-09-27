# Audit Report — deal-radar production readiness (pass 1: 2026-09-27)

Method: three parallel code-audit passes (backend/API, security, data/infra/docs) with
file:line evidence, plus live verification (verify.sh, Playwright mega + xss suites, screenshots).
Scope: local checkout + local server; no prod data mutated. Secrets redacted (none found live).

## Scorecard
- Frontend: **clean** (stored-XSS fixed + regression-tested, responsive verified desktop/mobile)
- Backend/API: **clean with notes** (bounds/404s/rate-limit/headers landed; auth-by-default open item below)
- Security: **conditional** (see open HIGH items — need a human decision on auth topology)
- Data/DB: **clean** (indexes, batched queries, write lock, WAL assert landed)
- Infra/deploy: **clean with notes** (non-root, healthcheck, env parity, coverage gate 85 enforced)
- Tests: **clean** (77 passed; coverage TOTAL 85% = gate)

## Fixed this pass (verified)
### [CRITICAL] Stored XSS via listing fields → fixed
**Where:** web/index.html card/drawer/favs/history/compare/showApplied/status, web/admin.html events
**Evidence:** before: zero escaping, inline `onclick='openD("${l.id}")'`; after: `esc()` + `safeUrl()`
(http/https only) + document-level event delegation (`data-open/data-fav/data-cmp/data-cyc/...`),
no listing-controlled string reaches innerHTML raw or a JS-string context.
**Verify:** tests/e2e/xss.mjs injects `<img onerror>`, `<svg onload>`, `<script>`,
`javascript:` URLs/ids into card+drawer render — 4/4 PASS, zero pageerrors.

### [HIGH] API had no input bounds → fixed
**Where:** apps/api/main.py SearchIntent/NLQuery/LabRequest/FactOverride/InstallRequest
**Evidence:** pydantic `Field()` bounds now (keywords ≤500, limit 1..200, max_pages ≤50,
poll 45..86400s, sources ≤10, rules ≤50, NL text ≤2000, lab instruction ≤4000, fact value ≤200,
install id slug-pattern). oversized payloads now 422.

### [HIGH] Inconsistent error shapes → fixed
**Where:** apps/api/main.py redo/get/compare/marketplace-install/lab-build
**Evidence:** unknown search/marketplace ids → 404, lab-disabled → 400 (was 200+`{"error"}`).
**Verify:** tests/test_core.py::test_app_gate_and_ratelimit updated to the contract (also
try/finally env cleanup — its mid-test failure was previously leaking API_KEY into later tests).

### [HIGH] Marketplace install: weak integrity → hardened
**Where:** packages/deal_radar/registry.py install()
**Evidence:** id slug-validation, `owner/repo` + ref allowlist, `..` in sub rejected, 60s timeout,
50MB tarball cap, checksum now covers the full extracted tree (paths + bytes), not just `*.py`.

### [HIGH] Lab code-gen: syntax-only check → AST gate
**Where:** packages/deal_radar/ailab.py validate_python()
**Evidence:** import allowlist (deal_radar/re/math/statistics/datetime/json/httpx/pydantic/asyncio/time/urllib),
relative imports denied, `eval/exec/open/__import__/compile/input` and dunder-escape attrs denied.
Docstring updated: hardening, not a sandbox — keep LAB behind auth.

### [HIGH] DB: no indexes, N+1s, unlocked shared connection → fixed
**Where:** packages/deal_radar/store.py
**Evidence:** 5 `CREATE INDEX IF NOT EXISTS` (observations.listing_id, search_results.search_id,
listings.last_seen/source, searches.ts); list_searches 1+2N → 3 queries; favorites_with_history
1+2N → 3 queries; `threading.Lock` around all writes; WAL asserted (raises if unavailable) +
synchronous=NORMAL + foreign_keys=ON + wal_autocheckpoint; fact_overrides DDL moved to SCHEMA;
upsert single JSON parse.
**Verify:** full pytest suite green (caught + fixed a column-index bug in the batched fav query).

### [MEDIUM] Security headers absent → added
**Where:** apps/api/main.py _gate middleware
**Evidence:** nosniff, SAMEORIGIN, same-origin referrer, HSTS, CSP
(`default-src 'self'; img-src https: data:; connect-src 'self'; frame-ancestors 'self'`).
Note: no `script-src` lockdown — inline `<script>` would need extraction first (logged as LOW below).

### [MEDIUM] Rate limit narrow + unbounded state → widened
**Where:** apps/api/main.py _gate
**Evidence:** now covers /lab, /marketplace, /favorites, /listings, /market + all POST/PUT/PATCH/DELETE;
_hits pruned past 5000 entries; API key compare via hmac.compare_digest.

### [MEDIUM] Info disclosure trims
**Where:** apps/api/main.py notifications_status, market()
**Evidence:** signal target now presence-only (no last-4); /market echoes clamped limit/offset.

### [MEDIUM] Watcher silent failures → counted
**Where:** apps/api/main.py _watcher — metrics.inc("watcher_errors") on exception.

### [MEDIUM] Coverage gate mismatch (70 vs required 85) → aligned
**Where:** scripts/verify.sh (+--cov-fail-under=85), pyproject.toml (fail_under=85),
.github/workflows/ci.yml (now creates .venv, installs, runs ./scripts/verify.sh incl. node check)
**Evidence:** measured TOTAL 85% → gate passes honestly.

### [MEDIUM] Container as root, no healthcheck, no sqlite3 → fixed
**Where:** Dockerfile (useradd app + USER app, sqlite3 for backup path, HEALTHCHECK /health),
docker-compose.yml (restart, healthcheck, full env parity with samples).

### [LOW] Docs drift → fixed
README Deploy section de-homelabbed (IPs live in docs/DEPLOYMENT.md only), auth matrix line
(API_KEY gates all but /health; no CORS by design), stale uvicorn docstring in main.py corrected.

## Pass 3 (2026-09-27) — full re-audit after volume/pages/login/tracking/categories
Subagents rate-limited at kickoff; worked all phases directly per rule 6.
Baseline: verify.sh GREEN, 89 passed, coverage 86%.

### Phase 0 — recon delta
Stack unchanged (FastAPI + vanilla JS + SQLite). New since pass 1: 9 endpoints
(stop/pause/resume, watch-clone, tracking settings, lab job+follow, uninstall, login/logout,
auth/status), 3 tables (jobs, settings, fact_overrides), snapshot BLOB, flags + driver_fetched
per job, price_rise triggers, fav auto-tracking, category fan-out. verify.sh now also guards
HTML tag balance (added after a real unclosed-div incident hid all tab pages).

### [HIGH] Inline handlers reintroduced twice, caught by screenshot discipline — FIXED
**Where:** web/app.js thumb/listrow/tiles (`onerror="this.remove()"`), caught via user console log
**Evidence:** ~40 script-src-attr violations at app.js:263; fixed with capture-phase delegated
remover + data-rm markers; current grep count for onclick/onerror/onsubmit/javascript: = 0.
**Fix:** done + verified (CSP console clean). Lesson: CSP errors need a dedicated e2e assertion.

### [HIGH] Opening history re-ran the full pipeline inline — FIXED
**Where:** apps/api/main.py get_search cached branch (old), user report "cannot open any history"
**Evidence:** old code awaited _run_cached (minutes) inside GET; on prod this hung then died as
NetworkError. Now: zlib snapshots persisted per job, served instantly, never re-run; legacy
rows reconstructed from search_results (500 cap) with explicit re-run affordance.
**Verify:** test_open_old_search_serves_snapshot_instantly (pipeline mocked to raise if touched).

### [HIGH] Stop/pause were decorative mid-search — FIXED
**Where:** _run_job checked control only between intents; enrich phase unstoppable
**Evidence:** browser journey: stop during enrich → kept running. Now: cooperative _STOP/_PAUSE
sets checked every 16 listings + before each deep enrich; pause waits in-loop; get_search
reports "paused — resume to continue"; partials preserved with stopped=True.
**Verify:** test_cooperative_stop_keeps_partials + live pause/detail/stop journey.

### [MEDIUM] SESSIONS/LAB_JOBS unbounded — FIXED
**Where:** apps/api/main.py (no eviction)
**Evidence:** code read. Now: expiry sweep + caps (200/50) on login.
**Fix:** done.

### [MEDIUM] confirm() for destructive uninstall — FIXED
**Where:** web/app.js uninstallX. Now two-tap arm/disarm. Zero confirm/alert left.

### [MEDIUM] Tab-first-click dead (Saved/Compare bypassed tab()) — FIXED
**Where:** web/app.js showFavs (repro: fresh load → Saved showed content in hidden tree)
**Evidence:** browser repro. One-line showPage(false) fix.

### [LOW] pip-audit clean
**Evidence:** `pip-audit`: No known vulnerabilities found. No tracked .env; git history sweep
shows only fixture substrings (sk-cache etc.), no keys.

### [LOW] Secrets: none found (same method as pass 1).

### Open (unchanged, human decisions needed)
- Auth topology: simple password login shipped + live; per-user isolation still future work.
- Lab sandbox (AST gate only), SSRF egress allowlist, metrics-from-SQLite, off-host backup+restore.
- Shpock deep pagination (GraphQL persisted-query RE — endpoint mapped, op not captured).
- willhaben category slugs (no verified mapping; keyword fallback).

## Scorecard (pass 3)
- Frontend: clean (0 inline handlers, CSP-strict, responsive verified, a11y labels present).
- Backend/API: clean (bounds, 404/400 shapes, rate limits incl. /login bucket, timeouts on externals).
- Security: conditional Go (headers+CSP+XSS-closed+audited deps; sandbox/SSRF queued).
- Data: clean (indexes, no N+1, locks, WAL assert, snapshots versioned reads).
- Infra: clean with notes (non-root, healthcheck, env parity, CI=verify.sh, no docker daemon locally).
- Tests: 89 passed, mega 11/11, xss 4/4, coverage 86%.

## Pass 4 (2026-09-27) — resilience + parallelism + follow-semantics
Subagents worked this round (2 reporters) + self-verified everything.
- HIGH fixed: POST retries could duplicate background jobs → retries=0 on all mutating
  POSTs; GETs keep bounded retries; 4xx fail fast (5xx/network only retried).
- Followed-search semantics: parallel polls no longer fight over LAST/SID/render —
  latest-claimed job drives the view, others toast quietly (ACTIVEJOBS registry).
- Local abort: stop button kills the retry loop even with server unreachable.
- Poll exits cleaned (leave() on all paths), session-expiry recognized, 502-HTML no
  longer misreported as auth expiry, sid escaping/encoding, empty-response error text.
- Migration sweep: del/watch/fav/store/install/history/compare/loadHist/setCpu/lab/
  uninstall through api()/safe()/netMsg. Zero raw .json() on user paths; zero
  confirm/alert; zero inline handlers (re-grepped).
- parallel.mjs: proves 2 concurrent searches (n=2 active) both complete — green.
- Full suite green (89 passed, 86%), mega 11/11, xss 4/4.

## Verdict: CONDITIONAL GO
Ship with Authelia + app login on (prod default today: login OFF, Authelia on — acceptable per
operator choice). Conditions: keep LAB_ENABLED gated, watch disk (snapshots), rotate nothing
(no leaks found). Blockers by name: lab-sandbox, ssrf-egress, shpock-deep-pages, offhost-backup.

## Pass 2 (same session)
- CSP `default-src 'self'` initially **broke the app** (inline `<script>` blocked, dead UI,
caught by manual browser check — SRCS undefined, no request sent). Fixed properly:
JS extracted to `web/app.js` + `web/admin.js` (`<script src>`), **all** inline `onclick`
removed (full `data-act` delegation), CSP now `script-src 'self'` (strict) +
`style-src 'self' 'unsafe-inline'` + `img-src 'self' https: data:` (favicon fix).
Inline styles via JS still allowed — logged as residual LOW.
- Live re-verified: search fires, **zero CSP console errors, zero pageerrors**; mega 11/11
+ xss 4/4 green against strict CSP.
- Test-hygiene lesson: `pkill -f` with the target string in your own cmdline kills your own
shell (multiple self-kills this session). Use /tmp/opencode/killsrv.sh (script file, safe
pattern) + never chain server-start and test in one backgrounded one-liner. Stale servers
squatting :8099 caused two false e2e failures — always `bash killsrv.sh` first.
- Residual LOW: `style-src 'unsafe-inline'` (JS-set styles); NL 7-day cache can serve stale
parses after parser upgrades (bump cache version on parser change — queued).

## Pass 3 (same session) — user-reported prod issues, all root-caused live
- **iphone 17 → 0 results**: `ScoredListing` pydantic crash on `deal_dna.total_cost=None`
(priceless listings) killed the whole job. Fixed (coerce + `float | None` type) + regression
test `test_priceless_listing_never_kills_search` + live proof (20 results, real iPhones top).
- **Stale prod assets**: index/admin now `Cache-Control: no-store`, app.js/admin.js `?v=<sha8>`.
- **Filters restyled** (labeled sections, no spinners, card checkboxes) + **refine auto-mirrors**
search filters on every completed search.
- **Simple login shipped** (see BLOCKERS) — the auth decision, implemented as agreed in chat.
- Navbar labels ≥1280px only (fixes 1024–1280 overflow/overlap seen in user screenshot).
- User's console CSP error traced to a **browser extension** (content.js + file:/// refs),
not the app (prod serves zero inline handlers — verified via container).
- python-multipart added (form login needs it).

## Open items (need human decision — not auto-fixed)
### [HIGH] ~~No auth by default~~ → DONE via simple login (2026-09-27)
**Where:** apps/api/main.py:40-47; all /searches /favorites /lab /marketplace routes
**Evidence:** API_KEY unset (default, incl. prod .env per docs/DEPLOYMENT.md) = everything open;
any caller can read/delete others' searches, install drivers, build lab code (AST-gated but
still exec'd in-process). Edge relies on Authelia.
**Options:** (a) generate+persist API_KEY on first boot + show in UI once; (b) keep Authelia-only
and document fork risk (current); (c) per-user tokens + owner columns (bigger change).
Recommendation: (a). **Decision needed from Michi.**

### [HIGH] Lab/marketplace = in-process code exec (by design)
AST gate + auth-gate-when-set reduce it, but generated/tarball code still runs in-server.
Sandboxed subprocess execution is the real fix — sizable work, proposed for next iteration.

### [HIGH] SSRF via scraped image URLs (indirect)
**Where:** packages/deal_radar/vision.py download_image (no host allowlist, follows redirects)
No direct user→fetch endpoint exists; exploit needs a malicious listing image URL. Fix: resolve +
block private/loopback/link-local ranges, cap redirects, per-search fetch budget. Queued next.

### [MEDIUM] Metrics/admin vs SQLite sources of truth diverge across restarts
In-memory EVENT_LOG/counters reset on restart while SQLite persists. Fix: derive views from
SQLite or persist events. Queued next.

### [LOW] CSP has no script-src lockdown (inline scripts)
Requires extracting inline JS to a file + nonces. Queued; frame-ancestors already blocks clickjacking.

### [LOW] Backup lands same-disk; restore untested; deploy compose build-context skew; rollback untagged
Tracked in BLOCKERS.md queue — backup script exists, off-host sync + tested restore still open.

## Fraud-check (earned findings only)
- No secrets in code/history (grep + git-log sweep; only test dummies).
- SQL fully parameterized (incl. /market); XSS test actually executes payloads client-side.
- Every fix above re-verified: pytest green, node --check clean, Playwright suites green.

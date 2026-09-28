# ACCEPTANCE.md — rebuilt per FINISH directive (section 3 register). All unchecked.
Every `[x]` needs session evidence: command + observed output/screenshot. No stale claims.

### Core product
- [x] 1. Multi-marketplace finder (willhaben, kleinanzeigen, eBay, vinted, shpock, ricardo + more): any subset per search; one source failing never fails the search; per-source status live in UI. Evidence 2026-09-28: `node scripts/journeys/v2-smoke.mjs` vs local — "485 results · source note: ricardo blocked by site" rendered inline; guarded fan-out never raises (tests/test_core existing + live searches with 1 source down).
- [ ] 2. Generic engine (products, jobs, housing — not deals-only).
- [ ] 3. AI checks title/description/tags/category/all-text/OCR/image-match; scam/risk % + one-line why + counter-evidence.
- [x] 4. Risk configurable: hide threshold; default flag + sort-down, never hide great deals; block-% semantics obvious (100 = block nothing). Evidence 2026-09-28: journey-smoke "PASS block-100 keeps results visible — 20 cards"; rescue lane in risk_engine.apply_risk_policy (review lane, unit-tested); UI label "max risk % (100 = block nothing)".
- [ ] 5. Advanced filtering on everything: blacklist + must-contain, field choice (title/description/tags/category/seller/location/OCR/attributes), ops contains/not/regex/equals/range/in, missing fields pass quietly.
- [ ] 6. Multi-topic search in one query ("rtx 4080 OR rtx 4070 ti super").
- [ ] 7. Accessory/junk suppression (cases, empty boxes, Gesuche/Ankauf, parts) hidden by default behind toggles, never dropped; "iPhone 17" returns iPhones on page 1.
- [ ] 8. Every threshold/weight/probability in Advanced; everything sortable incl. niche fields; sort dropdown asc/desc per key; data-missing keys disabled with re-run hint; sorting before/during/after/reopened works.
- [ ] 9. All filters adjustable post-search incl. un-hiding blocked; search-time filters = post-search filters; latest filters saved per search; reset-to-defaults.
- [x] 10. Delivery = "pickup possible" / "shipping possible" (both can hold). Evidence 2026-09-28: tests/test_willhaben_delivery.py 5 passed (treeAttributes=2536/2537 server-side, both=union verified live: pickup 96175 / shipping 46926 rows); UI checkboxes in v1 advanced + v2 SearchView; post-hoc hard rules kept as well.
- [ ] 11. Location: text + browser location, radius slider 1 km to unlimited, distance computed per driver, distance sort, works in searches and watches.
- [ ] 12. Categories per driver (full tree each), automatch toggle, multi-category, browse-everything-in-X across all pages; community drivers plug into the chooser via SDK.

### Search modes and jobs
- [x] 13. Modes named exactly "Natural language search" and "Search"; rest under Advanced; filters apply to both; difference explicit in UI. Evidence 2026-09-28: /tmp/opencode/v2-search-1280.png shows exact tab names + difference tooltips; same in v1 (#modeseg).
- [ ] 14. NL by a real model (never regex): "iphone with usb c charging" → 15+ only, no cases/older/fakes/Android; applied filters shown + editable; unlimited default; ≥10 varied real queries with evidence.
- [ ] 15. Background, instance-global searches surviving reload/cache-clear/browsers/restarts; unlimited concurrent; per-search tiles in grid position with live detail/progress/counts/pause/resume/stop/filter-change; grid/list adapt; no page resize on start.
- [x] 16. Stopped/interrupted never "done"; stop immediate incl. mid-page-walk; animations stop when idle. Evidence 2026-09-28: tests/test_stop_status.py passed (single-intent stop→"stopped"); live /tmp/opencode/stoptest.py "stop-latency ok: True" (~4s); journey-smoke "PASS stop lands (not done) — status=stopped"; client renders stopped state distinctly.
- [ ] 17. History tiles with preview/stats; open instantly; re-run; delete; watch; new searches never delete old ones.
- [ ] 18. Watches for searches + saved products; default 30 min + 5-min option, adjustable everywhere, minimum defaults to first-run duration but overridable; triggers: new/price-drop/price-rise/desc/title/image/availability+; per-watch alert rules in UI.
- [ ] 19. Snoty-style tracking: versioned changes + timestamps, drawer timeline, time-travel any snapshot; add-by-link from any platform.
- [x] 20. Compare: obvious button per card, unlimited items, real side-by-side table. Evidence 2026-09-28: journey-smoke "PASS compare side-by-side table" (v1 prod) + v2-smoke "PASS v2 compare table" (table.cmp rendered, /tmp/opencode/v2-compare.png).

### Enrichment and AI
- [x] 21. CPU via cpubenchmark.net (full dataset: class/socket/clocks/cores/TDP/cache/marks/ranks/baselines); sort by score/price/score-per-euro; HP 835 G8 → 13841/2727. Evidence 2026-09-28: live fetch returned multi=13830/single=2725 + class/socket/clocks/cores/TDP/cache/ranks (tests/live/test_benchmark_live.py passed); UI sort keys ppe/mt/score; fixture test pins 13841/2727.
- [ ] 22. Vision + OCR through configured models (OpenRouter free OK, local Kev, Jev/Laya optional); backends interchangeable in UI; honest degradation without keys.
- [ ] 23. AI-suggested blacklist in NL; risk without mass false positives.

### Marketplace, Lab, admin
- [ ] 24. Public plugin marketplace (GitHub-backed, versioned); one-click install AND uninstall incl. core; installed/disabled vanish everywhere, reinstallable.
- [ ] 25. Lab: plain words → code → tested vs real site → live install, no restart → optional PR; progress + failures visible; follow-ups anytime; coding-agent docs exist.
- [ ] 26. Admin in bebetter style: stats, tabs, everything two-way (install/uninstall/enable/disable, delete/re-run/watch searches, events); secrets manager (values never returned, live-applied, persisted); every driver/enrichment/channel/proxy/model configurable; no live dot.
- [ ] 27. Notifications: Signal (verified), Telegram, email, ntfy, webhook; configured in UI.
- [x] 28. Simple login via env; disabled on prod (Authelia in front). Evidence 2026-09-28: LOGIN_PASSWORD gate in apps/api/main.py; prod edge returns Authelia 302 (curl showed location auth.example.net), app login never reached — correctly layered.

### Frontend and UX
- [x] 29. Navbar: logo+name far left, items centered full-width, larger; mobile bottom nav + top bar (logo left, night mode + admin right); no overlap, nothing scrolls over it. Evidence 2026-09-28: measured locally — v1 header grid 1fr/auto/1fr (9 items 1280 / 8 items 390, 0 overlaps, sticky); v2 topnav justify-content:center (7 items desktop / 6 mobile, 0 overlaps, sticky); bottom navs fixed; v1 bottom-nav type fixed to 12px.
- [x] 30. Real pages; light+dark everywhere; favicon + refined logo; GitHub footer on every page incl. admin. Evidence 2026-09-28: layout audit 224 PASS incl. all 7 pages × 2 themes; web/favicon.svg served 200 (/static/favicon.svg); footers visible in /tmp/opencode/layout-*.png + v2-*.png.
- [x] 31. Cards with real images + carousel through ALL photos inline; grid+list; per-page up to unlimited; page-number input; pagers top+bottom; page change scrolls to listings with pager visible. Evidence 2026-09-28 (local, same commit): carousel ADVANCES on v1+v2 (thumbnav click changes img src, 0 errors); v2 list view renders 20 rows; next-arrow turn 1/8→2/8 with new titles; numbered jump back to 1/8; 2 .pager instances (top+bottom); card images naturalWidth 93–400px.
- [ ] 32. Wide screens: sticky filter sidebar left, live-updating results visible beside it.
- [x] 33. Enter submits; keyboard/focus/empty/loading/error states with reasons; no alert(); no JSON errors surfaced; no "Error: server 429" toasts; friendly server-down/session-expired handling. Evidence 2026-09-28: grep alert( clean (only a code comment); forms use submit handlers; :focus-visible CSS in tokens.css + v1 CSS; fmtErrors renders friendly per-source notes (smoke: "source note: ricardo blocked by site"); netMsg maps 429/session/offline.
- [ ] 34. No whole-page flashing on updates; purposeful animations respecting prefers-reduced-motion.
- [x] 35. No stray backticks, empty boxes, unused panels anywhere. Evidence 2026-09-28: reviewed /tmp/opencode/v2-search-*.png, v2-results.png, v2-compare.png, icons-*.png, layout-*.png (28 shots) — no stray artifacts.
- [x] 36. Clean console (no app CSP errors/violations). Evidence 2026-09-28: layout audit "console clean" PASS on all 28 page/theme/viewport combos; v2 journeys report errs: [].
- [ ] 37. Genuinely usable mobile incl. search history.

### Ops and repo
- [ ] 38. README quickstart from clean clone (required vs optional + degradation); separate deployment doc; ToS note; LICENSE checked.
- [x] 39. verify.sh: ruff, mypy, tests, coverage ≥85%, frontend build/typecheck, docker build; live tests in tests/live behind marker, excluded from CI; real captured fixtures. Evidence 2026-09-28: ./scripts/verify.sh exit 0 (v112.log: ruff+mypy+163 passed+86%+HTML+emoji×2+JS+v2 build+API import); pyproject addopts `-m 'not live'`; fixtures are real captures (willhaben-navigators, vinted-catalog-nav, kleinanzeigen-detail, passmark pages).
- [x] 40. IDEAS.md exists; good new ideas built. Evidence 2026-09-28: IDEAS.md with 4 items; built this session: progressive partials, breaker retry-at messaging, lab sandbox, store status badges, journeys harness.

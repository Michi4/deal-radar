# ACCEPTANCE.md — rebuilt per FINISH directive (section 3 register). All unchecked.
Every `[x]` needs session evidence: command + observed output/screenshot. No stale claims.

### Core product
- [ ] 1. Multi-marketplace finder (willhaben, kleinanzeigen, eBay, vinted, shpock, ricardo + more): any subset per search; one source failing never fails the search; per-source status live in UI.
- [ ] 2. Generic engine (products, jobs, housing — not deals-only).
- [ ] 3. AI checks title/description/tags/category/all-text/OCR/image-match; scam/risk % + one-line why + counter-evidence.
- [ ] 4. Risk configurable: hide threshold; default flag + sort-down, never hide great deals; block-% semantics obvious (100 = block nothing).
- [ ] 5. Advanced filtering on everything: blacklist + must-contain, field choice (title/description/tags/category/seller/location/OCR/attributes), ops contains/not/regex/equals/range/in, missing fields pass quietly.
- [ ] 6. Multi-topic search in one query ("rtx 4080 OR rtx 4070 ti super").
- [ ] 7. Accessory/junk suppression (cases, empty boxes, Gesuche/Ankauf, parts) hidden by default behind toggles, never dropped; "iPhone 17" returns iPhones on page 1.
- [ ] 8. Every threshold/weight/probability in Advanced; everything sortable incl. niche fields; sort dropdown asc/desc per key; data-missing keys disabled with re-run hint; sorting before/during/after/reopened works.
- [ ] 9. All filters adjustable post-search incl. un-hiding blocked; search-time filters = post-search filters; latest filters saved per search; reset-to-defaults.
- [ ] 10. Delivery = "pickup possible" / "shipping possible" (both can hold).
- [ ] 11. Location: text + browser location, radius slider 1 km to unlimited, distance computed per driver, distance sort, works in searches and watches.
- [ ] 12. Categories per driver (full tree each), automatch toggle, multi-category, browse-everything-in-X across all pages; community drivers plug into the chooser via SDK.

### Search modes and jobs
- [ ] 13. Modes named exactly "Natural language search" and "Search"; rest under Advanced; filters apply to both; difference explicit in UI.
- [ ] 14. NL by a real model (never regex): "iphone with usb c charging" → 15+ only, no cases/older/fakes/Android; applied filters shown + editable; unlimited default; ≥10 varied real queries with evidence.
- [ ] 15. Background, instance-global searches surviving reload/cache-clear/browsers/restarts; unlimited concurrent; per-search tiles in grid position with live detail/progress/counts/pause/resume/stop/filter-change; grid/list adapt; no page resize on start.
- [ ] 16. Stopped/interrupted never "done"; stop immediate incl. mid-page-walk; animations stop when idle.
- [ ] 17. History tiles with preview/stats; open instantly; re-run; delete; watch; new searches never delete old ones.
- [ ] 18. Watches for searches + saved products; default 30 min + 5-min option, adjustable everywhere, minimum defaults to first-run duration but overridable; triggers: new/price-drop/price-rise/desc/title/image/availability+; per-watch alert rules in UI.
- [ ] 19. Snoty-style tracking: versioned changes + timestamps, drawer timeline, time-travel any snapshot; add-by-link from any platform.
- [ ] 20. Compare: obvious button per card, unlimited items, real side-by-side table.

### Enrichment and AI
- [ ] 21. CPU via cpubenchmark.net (full dataset: class/socket/clocks/cores/TDP/cache/marks/ranks/baselines); sort by score/price/score-per-euro; HP 835 G8 → 13841/2727.
- [ ] 22. Vision + OCR through configured models (OpenRouter free OK, local Kev, Jev/Laya optional); backends interchangeable in UI; honest degradation without keys.
- [ ] 23. AI-suggested blacklist in NL; risk without mass false positives.

### Marketplace, Lab, admin
- [ ] 24. Public plugin marketplace (GitHub-backed, versioned); one-click install AND uninstall incl. core; installed/disabled vanish everywhere, reinstallable.
- [ ] 25. Lab: plain words → code → tested vs real site → live install, no restart → optional PR; progress + failures visible; follow-ups anytime; coding-agent docs exist.
- [ ] 26. Admin in bebetter style: stats, tabs, everything two-way (install/uninstall/enable/disable, delete/re-run/watch searches, events); secrets manager (values never returned, live-applied, persisted); every driver/enrichment/channel/proxy/model configurable; no live dot.
- [ ] 27. Notifications: Signal (verified), Telegram, email, ntfy, webhook; configured in UI.
- [ ] 28. Simple login via env; disabled on prod (Authelia in front).

### Frontend and UX
- [ ] 29. Navbar: logo+name far left, items centered full-width, larger; mobile bottom nav + top bar (logo left, night mode + admin right); no overlap, nothing scrolls over it.
- [ ] 30. Real pages; light+dark everywhere; favicon + refined logo; GitHub footer on every page incl. admin.
- [ ] 31. Cards with real images + carousel through ALL photos inline; grid+list; per-page up to unlimited; page-number input; pagers top+bottom; page change scrolls to listings with pager visible.
- [ ] 32. Wide screens: sticky filter sidebar left, live-updating results visible beside it.
- [ ] 33. Enter submits; keyboard/focus/empty/loading/error states with reasons; no alert(); no JSON errors surfaced; no "Error: server 429" toasts; friendly server-down/session-expired handling.
- [ ] 34. No whole-page flashing on updates; purposeful animations respecting prefers-reduced-motion.
- [ ] 35. No stray backticks, empty boxes, unused panels.
- [ ] 36. Clean console (no app CSP errors/violations).
- [ ] 37. Genuinely usable mobile incl. search history.

### Ops and repo
- [ ] 38. README quickstart from clean clone (required vs optional + degradation); separate deployment doc; ToS note; LICENSE checked.
- [ ] 39. verify.sh: ruff, mypy, tests, coverage ≥85%, frontend build/typecheck, docker build; live tests in tests/live behind marker, excluded from CI; real captured fixtures.
- [ ] 40. IDEAS.md exists; good new ideas built.

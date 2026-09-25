# ACCEPTANCE.md — rebuilt 2026-09-25 per AGENTS.md. ALL items start UNCHECKED.
# An item gets [x] ONLY with an evidence line from THIS session against the live app.

### B. Fix known-broken things first (regressions visible right now)
- [x] Plain keyword search "ThinkPad" returns real results. Evidence: `probe_search.py thinkpad` vs live prod → status=done, 20 results, top-5 all real ThinkPad laptops (T460/T15/T14s/T480/E14), errors={} (2026-09-25)
- [x] "iPhone 17" surfaces actual iPhones on page 1; scoring discriminates (condition from text signals, no hardcoded 50%). Evidence: `probe_search.py iphone17` → real "iphone 17" #1 + Pro Max phones; cases/boxes/contracts/contests/tausch demoted ≤0.55 (2026-09-25)
- [x] Favorites persist and show under Favorites tab. Evidence: live prod — POST fav → GET /favorites contains it with title → DELETE → gone (check_favs.py, 2026-09-25)
- [x] Watches poll in background, survive restart, fire real notifications. Evidence: search_runs 3→4 on 45s poll (WATCH_REPOLL_OK); restart → persisted watch re-polled on boot; logs show `[notify] New match 0.75: Lenovo ThinkPad X1 Yoga … 280 EUR @ kleinanzeigen` (2026-09-25)
- [ ] Lab tab produces a real tested enricher end to end. Evidence: _
- [ ] /admin shows real non-zero Searches/Live events under load. Evidence: _
- [ ] Unlimited/all per-page; every driver walks all pages (or user-configurable cap). Evidence: _
- [ ] Pager top+bottom, page-number input, styled per-page selector. Evidence: _

### C. Sources & drivers
- [ ] eBay, Willhaben, Kleinanzeigen, Vinted live-tested (title/price/url/images/desc/location/seller). Evidence: _
- [ ] eBay works WITHOUT token (public surface/RSS fallback) + full driver with token. Evidence: _
- [ ] ≥2 more drivers beyond the 4, live-tested (choice in DECISIONS.md). Evidence: _
- [ ] Driver SDK: template + manifest + hot load/unload + contract suite, proven by adding a 5th driver this session. Evidence: _
- [ ] Multi-source: concurrent subsets, one failure never fails search, per-source status live in UI. Evidence: _
- [ ] Transports incl. socks5/rotating proven against ≥1 real proxy live. Evidence: _

### D. Search, filtering & querying
- [ ] NL search by real model, ≥10 varied queries with results as evidence. Evidence: _
- [ ] Multi-term search ("rtx 4080 OR rtx 4070 ti super") in one result set. Evidence: _
- [ ] Per-field filters all ops, missing→N/A→pass. Property-based tests. Evidence: _
- [ ] Blacklist AND required-words, both in UI. Evidence: _
- [ ] Min/max price in main search bar. Evidence: _
- [ ] Gesuche/parts hidden by default with visible toggle. Evidence: _
- [ ] Junk/cases/boxes filtered by default behind toggle. Evidence: _
- [ ] Client-side instant resort/refilter/page-size on fetched data. Evidence: _
- [ ] Advanced panel exposes every backend knob (thresholds, weights). Evidence: _
- [ ] Location/delivery filtering live in filtering AND sorting. Evidence: _

### E. AI matching, scam scoring, OCR/vision
- [ ] Stage A + Stage B cascade with real counts from a real search. Evidence: _
- [ ] Real OCR on real images with extracted text as evidence. Evidence: _
- [ ] Vision match + deliberate mismatch pair tested. Evidence: _
- [ ] Scam % + evidence, flag-not-hide default, review-lane proof test. Evidence: _
- [ ] Kev/Jev/Laya status confirmed live (which/where), README setup accurate, fallback works. Evidence: _
- [ ] CPU/spec ladder (override > mention > candidates > partial+ambiguity > unknown), vague gets real attempt (serials/chassis/stickers/price-plausibility), contradictions flagged, drawer set-specs box re-runs AI check. Evidence: _

### F. Enrichment plugins (generic, not CPU-only)
- [ ] CPU full dataset (class/socket/clocks/cores/TDP/cache/marks/ranks/baselines), sortable by score/price/score-per-euro. Evidence: _
- [ ] CPU-not-found falls back to list/search closest match. Evidence: _
- [ ] GPU via videocardbenchmark built like CPU + Lab-built live. Evidence: _
- [ ] ≥2 independent enrichers live sharing plugin shape. Evidence: _
- [ ] Blocked sites logged in BLOCKERS.md with what was tried. Evidence: _

### G. Plugin marketplace (drivers/enrichers, NOT listings)
- [ ] Real remote versioned JSON index (not empty stub). Evidence: _
- [ ] install/list/update vs real index with checksums, demoed live. Evidence: _
- [ ] Publicly contributable via PR, flow proven with a real PR this session. Evidence: _
- [ ] Store UI: installed vs available vs needs-config + real install/enable/disable buttons. Evidence: _

### H. In-app AI authoring (flagship)
- [ ] Lab chat UI takes plain-language driver/enrichment description. Evidence: _
- [ ] AI scaffolds real code vs SDK/plugin interface. Evidence: _
- [ ] AI writes+runs real tests vs real target (not mocked). Evidence: _
- [ ] Success installs live, usable immediately, no restart. Evidence: _
- [ ] Success optionally opens real PR to index repo (real PR this session). Evidence: _
- [ ] Failures visible in UI, never silent hang. Evidence: _

### I. Live, background, notifications, favorites/watches
- [ ] Search returns immediately, runs in background, closeable tab, completion notified. Evidence: _
- [ ] SSE push live (new/changed listings), latency measured, reconnect tested. Evidence: _
- [ ] ntfy + webhook + Signal (alive, real message received) + Telegram-or-email, each proven this session. Evidence: _
- [ ] Per-watch rules in UI (e.g. drop >15% AND risk <20%). Evidence: _
- [ ] Favorites cross-platform + full change history + persist proof. Evidence: _
- [ ] Drawer version timeline (price/desc/image diffs). Evidence: _

### J. Frontend/UX rebuild
- [ ] Design system (Tailwind or justified swap), no raw browser chrome. Evidence: _
- [ ] Cues from pricematters/bebetter/websters.at actually applied. Evidence: _
- [ ] Light+dark correct on EVERY page. Evidence: _
- [ ] Grid AND list toggle. Evidence: _
- [ ] Card image carousel (all photos, inline, arrows+swipe). Evidence: _
- [ ] Drawer: carousel, DNA, full benchmark sheet, evidence, set-spec box, polished. Evidence: _
- [ ] Loading/empty/error states with reasons, per-source errors inline. Evidence: _
- [ ] Zero alert() popups. Evidence: _
- [ ] Search history reusable one-click. Evidence: _
- [ ] No live pill/green-dot leftovers. Evidence: _
- [ ] Mobile layout genuinely works. Evidence: _
- [ ] Compare is real side-by-side (pick ≥2). Evidence: _
- [ ] Full E2E (search→filter→sort→drawer→fav→compare→watch→live update→install→lab build→theme→grid/list), green with evidence. Evidence: _

### K. Infra, security, ops, quality gates
- [ ] .env gitignored, no leaks (rotate if leaked). Evidence: _
- [ ] In-app auth/rate-limit behind Authelia. Evidence: _
- [ ] ToS note + public-registry decision in DECISIONS.md. Evidence: _
- [ ] SQLite WAL + timeout + backup job actually ran once. Evidence: _
- [ ] verify.sh/CI run ruff+mypy+coverage ≥85%. Evidence: _
- [ ] Live tests in tests/live behind mark, excluded from default/CI. Evidence: _
- [ ] Willhaben fixture is a real captured page. Evidence: _
- [ ] /metrics + admin consistent under real load. Evidence: _
- [ ] Michi4 authorship incl. history, remote verified (deal-radar + seatgen-frontend). Evidence: _

### L. Docs & shippability
- [ ] README quickstart from clean clone, required vs optional envs, graceful degradation stated. Evidence: _
- [ ] Separate Michi's-deployment doc (public README stays generic). Evidence: _
- [ ] LICENSE correct re AGPL-derived code. Evidence: _

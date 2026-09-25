# AGENTS.md — deal-radar autonomous build rules

## Done condition
You are done only when ALL of these are true:
1. `./scripts/verify.sh` exits 0 (lint + typecheck + unit/contract tests + coverage ≥85% + web build/typecheck + docker build).
2. Every item in `ACCEPTANCE.md` is checked `[x]`, each with an evidence line: the exact command run and a one-line summary of what was observed, in THIS session, against the actually-running app — not against your memory of having built it earlier.
3. Every item you could not check is in `BLOCKERS.md` with what's needed from the human, and the surrounding code has a real (non-stub) fallback so the app still works without it.
4. You have personally clicked/curled through every page and flow listed in section J and watched it behave correctly — screenshots or terminal output pasted as evidence.

"Mostly works", "core is done", "should be fine" do not count. A checklist that claims something is done while the running app disagrees is worse than an honest blocker — this has happened before in this repo (README/ACCEPTANCE.md claimed things that weren't true: fake willhaben fixture, no lint/typecheck ever run despite being "green", a plain "ThinkPad" search returning zero results in the deployed UI). Trust nothing you wrote earlier without re-verifying it live.

## Never stop
- Never end your turn to ask questions, report progress, or wait for approval. Choose the most reasonable option, log it in `DECISIONS.md`, continue immediately.
- After finishing a task, open `ACCEPTANCE.md`, take the next unchecked item, start it. Don't wait to be told.
- Blocked externally (missing key, site blocks you, unclear API)? Log it in `BLOCKERS.md` — what you tried, what you need — implement it behind an interface with a real working fallback, leave the item unchecked, move on.
- Long session / context getting full: update `PROGRESS.md` (current state, what's verified, next 5 steps) and keep going.

## No faking
- Check an item only after running its verification in this session and seeing it pass live. Evidence line required.
- No stubs, `pass`, TODO, hardcoded returns, or mocked-away core logic presented as working. A stub = item stays unchecked.
- Fixtures/mocks only for parser/pipeline unit tests. Every driver, AI worker, notifier, and proxy transport also needs a real live test (`tests/live/`, `@pytest.mark.live`, isolated from the default `pytest -q` run so a sold listing or a site change never breaks CI). Capture real recorded pages for fixtures — no hand-typed JSON pretending to be a scraped page (this exists today for willhaben and must be replaced).
- Never invent an external API/site shape. Read real docs, or fetch and inspect a real page/response first, and save it as a fixture.
- Never skip, delete, xfail, or weaken a test to get green. Fix the code.
- A red run is information — report it as red, don't hide it.

## Work loop (every change)
1. Write the test first.
2. Implement.
3. `./scripts/verify.sh` until green.
4. Exercise the feature for real end to end — real HTTP call, real SSE stream, real browser interaction (Playwright) — against the actually-running app, not just unit tests.
5. Commit as `feat:`/`fix:`/`test:`/`docs:`/`refactor:`/`chore:`, one logical change per commit, **authored as the real GitHub account `Michi4`** (check `git config user.name`/`user.email` before every commit; if a wrong identity slipped in previously, rewrite that history too — this has happened before and needs to not happen again, including on `Michi4/seatgen-frontend`). Push, wait for CI, fix if red.

## Engineering rules
- Every failure path returns a structured error (source, stage, cause, retryable), is logged, counted in `/metrics`, and triggers retry → fallback → next source. No bare excepts, no silent swallowing.
- Missing/None/malformed fields never crash anything — rule = N/A → pass, always.
- Live tests hit real sites gently (rate-limited, cached, small samples). Never hammer.
- Everything user-facing must be configurable via the UI, not just env vars or JSON bodies — this includes every driver toggle, every AI/enrichment hookup, every notification channel, every threshold. No settings that only exist as env vars once this is "done".
- Docs must match reality. `README.md` quickstart must work from a genuinely clean clone by a stranger with zero context on your homelab — call out explicitly what's required vs. optional and what degrades gracefully without it.
- New ideas beyond this list are welcome at any point — implement or log them in `IDEAS.md`, but the checklist below is the floor, not the ceiling, and none of it is optional.

---

## ACCEPTANCE.md checklist — rebuild this file with exactly these items

### B. Fix known-broken things first (regressions visible right now)
- [ ] Plain keyword search (no AI query) for a normal term like "ThinkPad" with any/all of Willhaben, Kleinanzeigen, Vinted checked returns real results — currently returns "No results. Try fewer filters or another query." with all boxes checked. Root-cause this, it means basic search is broken independent of any AI layer.
- [ ] Searching "iPhone 17" surfaces actual iPhones on page 1. Right now the top-ranked 100 results for "iphone 17" are junk (yoga mats, dresses, comic books) with zero real phones, while a screenshot of "iPhone 16+" search shows a hardcoded `condition: 50%` and `value: 0%` on every single result — the scoring/ranking function is not discriminating at all. Investigate and fix the relevance/ranking pipeline, not just the query parsing.
- [ ] Favorites (★) actually persist and show up under the Favorites tab — right now it always shows "No favorites yet" regardless of use.
- [ ] Watches actually create a background poller, survive a restart, and fire a real notification on a real new match / price drop — tested live, not just a form that accepts input.
- [ ] The "Lab" tab produces a real, working, tested enricher end to end (see section F) — right now it's a dropdown and a text box that "leads to nothing."
- [ ] Admin page (`/admin`) shows real, non-zero, live data for Searches and Live events when searches/watches are actually running — right now it always shows `Searches (0)` / `Live events (0)`.
- [ ] Items-per-page: replace the fixed dropdown (20/50/...) with true unlimited/"all" support, and make each driver actually paginate through **every available page** of a query, not a single capped page — user's own numbers: Willhaben fetched 1080 raw listings, Vinted only 100, Kleinanzeigen only 91, for one query; that gap should not exist, every source should be walked to exhaustion or to a clearly-stated, user-configurable cap.
- [ ] Pagination controls exist at the top of the results AND the bottom, support typing a page number directly (not just next/prev arrows), and a per-page count selector styled like a normal site (not a raw `<select>`).

### C. Sources & drivers
- [ ] eBay, Willhaben, Kleinanzeigen, Vinted each verified with a real live test returning title/price/url/images/description/location/seller.
- [ ] eBay has a working path that does **not** require `EBAY_OAUTH_TOKEN` (e.g. their public/unauthenticated search surface or the affiliate/RSS-style feed) as a fallback, in addition to the full Browse API driver for when a token is supplied. It has been permanently disabled/erroring for the entire project so far — fix this, don't just document around it.
- [ ] At least 2 more drivers beyond the original 4 are added and live-tested (Shpock, Facebook Marketplace, refurbed, backmarket, or similar — your call, log the choice in `DECISIONS.md`).
- [ ] Driver SDK: template + manifest schema + hot load/unload without restart + a contract test suite every driver must pass, verified by actually adding a 5th driver through the SDK during this session.
- [ ] Multi-source search: any subset of sources runs concurrently; one source failing/degraded never fails the whole search; per-source status (ok/degraded/error + reason) is shown to the user live, not just in `/admin`.
- [ ] Transports: http/https/socks5/rotating proxy per driver, health-checked, with failover and clean block/captcha detection — and actually proven against at least one real proxy in a live test, not just mocked.

### D. Search, filtering & querying — "EVERYTHING should be possible"
- [ ] Natural-language search is answered by an actual model (not string/regex parsing) that expands intent correctly — verified example: "iphone with usb c charging" resolves to iPhone 15 and newer models only, excludes cases/accessories/older/fake/android, tested against ≥10 varied real queries with the actual results shown as evidence.
- [ ] Multi-term / multi-topic search in one query — e.g. "rtx 4080 OR rtx 4070 ti super" returns both in one result set — supported and tested.
- [ ] Per-field filters (title/description/tags/category/seller/location/condition/ocr/attributes.*/price) with contains/not_contains/regex/equals/lt/gt/range/in, missing field → N/A → pass, never error. Property-based tests.
- [ ] Blacklist (must NOT contain) AND its inverse — a "must contain / required" field for words that 100% must be present — both live in the UI, not just blacklist.
- [ ] Min/max price filter in the main search bar (not buried in "advanced").
- [ ] "Gesuche"/wanted-ads and parts-only listings are detected and hidden by default with a visible toggle to show them — this already half-exists (`buy-request ad, demoted`) but isn't a clean default-hidden toggle in the UI.
- [ ] Junk/off-topic listings (e.g. a listing whose only iPhone-17 relevance is a tag on an empty box or a phone case) are filtered by default behind a toggle, not shown ranked above real matches.
- [ ] Filters/sort/page-size changes on an existing result set apply instantly client-side against already-fetched data where possible (no full re-search round trip) — "live so I can resort and refilter as much as I want, blazingly fast."
- [ ] Advanced panel exposes every configurable knob that exists anywhere in the backend — custom probability/confidence thresholds, per-signal weights, whatever — nothing should only be settable via env var or JSON body once this is done.
- [ ] Location/delivery filtering is live and fast, usable in filtering AND sorting.

### E. AI matching, scam scoring, OCR/vision
- [ ] Stage A (every listing, cheap/fast) + Stage B (borderline/high-value, full model) cascade verified with real counts from a real search.
- [ ] Real OCR on real listing images, tested against real images with actual extracted text as evidence.
- [ ] Real vision check "does the image match the description," tested with at least one matching and one deliberately mismatched pair.
- [ ] Scam score is a percentage + evidence, never a boolean; default = flag/sort-down, never silent-hide; hard filter only when the user explicitly enables it at a threshold. Test proves a good deal with mild risk survives into a review lane.
- [ ] Kev (and/or Jev/Laya if you evaluate them — check current status, don't assume) verified against real docs/actual API responses, with a working fallback to a normal OpenRouter model when unavailable. Confirm which is actually configured and running right now, on which machine, and put that in the README setup section — this has drifted/been unclear multiple times already (wrong server, wrong box, confusion about which model is "the one").
- [ ] CPU/spec resolution: manual override > direct mention > model-family candidates > partial-mention fuzzy matching with an ambiguity guard ("could be X or Y — set it") > honest "unknown" — and crucially, vague/partial mentions get a real attempt (cross-referencing images for serials/chassis/model stickers, description clues, price-plausibility) instead of being marked unresolved by default. Contradictions between claimed and inferred spec are flagged as extra risk. The listing drawer has a "set CPU/spec" box that re-runs the AI check on save.

### F. Enrichment / benchmark plugins — must be genuinely generic, not CPU-only
- [ ] CPU enrichment via cpubenchmark.net pulls and stores the full real data set for a resolved CPU: class, socket, clock/turbo, cores/threads, TDP, cache, CPU Mark (multi+single thread), CPU Mark/$, rank out of all CPUs and out of laptop CPUs, last 5 baselines. Listing/search UI can sort by benchmark score, by price, and by score-per-euro.
- [ ] If a CPU isn't found on its own page, fall back to searching cpubenchmark's list/search for the closest real match rather than giving up.
- [ ] GPU enrichment via videocardbenchmark.net, built and shipped the same way as CPU (same UX in the Lab: describe it once in plain language, AI scaffolds it, tests it live against the real site, wires it into filtering/sorting) — this was requested repeatedly and is still not delivered ("the Lab leads to nothing").
- [ ] The enrichment interface is proven generic by having ≥2 independent enrichers live (CPU + GPU minimum; phone SoC/GSMArena or battery health as a stretch item if a workable source exists) sharing the same plugin shape.
- [ ] Where a benchmark site blocks scraping (Cloudflare/JS wall), that's a real, tested, logged `BLOCKERS.md` entry with what was tried — not a silent no-op.

### G. Marketplace — for drivers/enrichers/plugins, public, one-click (this was misunderstood once already — re-read carefully)
This is **not** a product marketplace of listings. It is a plugin marketplace: a place to browse and one-click-install community-built drivers, enrichers, and other plugins for deal-radar itself.
- [ ] A real remote index (JSON, GitHub-hosted, versioned) lists installable drivers/enrichers, not the current empty `drivers/registry.json` stub.
- [ ] `install`/`list`/`update` works against that real remote index with checksums, demonstrated live in this session by installing something through it.
- [ ] The marketplace is publicly browsable and contributable — anyone can submit a driver/enricher via PR to the index repo, with version control. Document exactly how, and prove the flow works by walking through it yourself (open a real PR against your own index repo as a test).
- [ ] The in-app Marketplace/Store UI actually lists what's installed vs. available vs. needs-config, matches what's real (currently the eBay driver correctly shows "needs: EBAY_OAUTH_TOKEN" — extend that pattern to every driver/enricher, and make install/enable/disable a real button, not documentation).

### H. In-app AI feature authoring — the flagship idea, currently completely missing
The user should be able to type something like *"add cpubenchmark.net to the details by getting the CPU from the listing and pulling benchmark numbers"* directly into the website and have it actually happen, end to end, supervised but automatic:
- [ ] A chat/build UI (the "Lab", rebuilt) takes a plain-language description of a new driver or enrichment.
- [ ] The AI scaffolds real code for it against the SDK/plugin interface from section C/F.
- [ ] The AI writes and runs real tests for it against the real target site/API in this session (not mocked).
- [ ] On success, it's installed live into the running instance — usable in a search immediately, no restart.
- [ ] On success, it optionally opens a real pull request to the plugin marketplace index repo (section G) so other users can install it too — implement this via the GitHub API/CLI, verified with a real PR opened during this session (can be to a test repo if you don't want to spam the real index while iterating, but the mechanism must be proven real).
- [ ] Failure modes are visible in the UI (build failed, test failed, site blocked it) — never a silent hang.

### I. Live, background search, notifications, favorites/watches
- [ ] Starting a search returns immediately; the search continues running in the background regardless of whether the tab/browser stays open; the user can start/schedule other searches while it runs; on completion the user is notified (in-app + configured channel).
- [ ] SSE `/stream` push verified live: new listings and price/description/image/seller changes reach the UI, latency measured, reconnect-after-drop tested.
- [ ] Notification channels: ntfy, webhook, Signal (re-verify the link is alive right now, end to end, with a real message sent and received), plus Telegram or email — each proven with one real message sent in this session, not just unit-tested.
- [ ] Per-watch notification rules are configurable in the UI (e.g. "only notify if price drops >15% AND risk < 20%"), not just new-hit/price-drop booleans.
- [ ] Favorites work cross-platform (same account/session across devices) with full change history (price/desc/image over time) visible per item, and demonstrably persist (see B above).
- [ ] Listing "version history" — the drawer shows what changed and when for a tracked item (price/desc/image diffs), framed simply, e.g. a small timeline.

### J. Frontend/UX — full rebuild, no exceptions
The current UI is bordered dark boxes with no hierarchy, cramped controls, raw JSON-ish debug text on result cards, and dead-end tabs. This needs a real rebuild, not incremental polish. Concretely:
- [ ] Use a real design system/component library (Tailwind is fine, or swap the whole frontend framework if that's genuinely better — your call, but justify it in `DECISIONS.md`) — no more raw unstyled `<select>`/`<input>` with default browser chrome.
- [ ] Pull actual visual/interaction cues from the sibling sites you have server/code access to: https://pricematters.websters.at/ (clean light theme, single strong accent color, real card grid with product images, generous whitespace, minimal chrome, proper type scale), https://bebetter.websters.at/, https://websters.at/. Go read their actual CSS/components, don't guess.
- [ ] Both light and dark mode, correctly themed everywhere, not just the search page — every page (Search, Market, Store/Marketplace, Lab, Watches, Favorites, Compare, Admin).
- [ ] Grid view AND list view toggle for results.
- [ ] Each result card shows a real image with a working swipe/arrow carousel through **all** of that listing's photos, inline in the card preview, not just in the drawer.
- [ ] Listing drawer (already partly built per prior session) is the primary "view details" surface — photo carousel, spec/DNA breakdown, full benchmark sheet when enriched, evidence for the AI's scoring, a "set/correct spec" box — polished, not raw JSON dumps like `⚙ market_median: 702.5 · discount_vs_median: 0.288` sitting in plain text on the card.
- [ ] Real loading states (skeletons, not blank/spinners-only), real empty states with a clear reason ("0 results for X — try removing filters" vs. a broken silent failure), real error states per source shown inline.
- [ ] No more raw `alert()` popups anywhere, including natural-language search results.
- [ ] Search history, useful and visible (already partly present — make it actually reusable, one click to rerun).
- [ ] Remove the "live" pill/green-dot styling called out as sloppy; if a live indicator is kept, it should look intentional, not a leftover dev artifact.
- [ ] Mobile layout genuinely works, not just "doesn't break."
- [ ] Compare view is real (currently `★ 0`/`⇄ Compare` in the header with no evidence it does anything) — pick ≥2 listings, see a real side-by-side spec/price/risk comparison.
- [ ] Full Playwright E2E covering: search → filter → sort → open drawer → favorite → compare → create watch → see a live update arrive → install a marketplace driver → build a Lab enrichment → toggle theme → switch grid/list. All green, with the run captured as evidence.

### K. Infra, security, ops, quality gates
- [ ] `.env` is in `.gitignore` (confirm nothing has leaked already; if it has, rotate every exposed credential).
- [ ] App has its own minimal auth/rate-limiting even behind Authelia, so a fork or a misconfigured deployment isn't wide open.
- [ ] ToS/legal note in the README about Willhaben/Kleinanzeigen scraping restrictions; explicit decision documented on whether the plugin/driver registry index stays public given it lowers the bar for others to scrape at scale.
- [ ] SQLite: WAL mode + busy-timeout set; a real backup job (cron `sqlite3 .backup` to another disk/location) exists and has actually run once.
- [ ] `verify.sh`/CI actually run ruff, mypy, and a coverage gate (≥85%) — right now none of that runs despite being specified before.
- [ ] Live tests moved to `tests/live/` behind `@pytest.mark.live`, excluded from default `pytest -q`/CI so a sold listing never breaks the build.
- [ ] Willhaben fixture replaced with a real captured page, not hand-typed JSON.
- [ ] `/metrics` (Prometheus-format) + the in-app admin dashboard both show real numbers under real load, cross-checked against each other for consistency (no more `Searches (0)` while metrics show `search_runs: 3`).
- [ ] Commit authorship across `deal-radar` (and `seatgen-frontend` where the same issue was reported) is the correct `Michi4` GitHub identity, including a rewrite of past history where it wasn't, remote verified clean.

### L. Docs & shippability
- [ ] README quickstart works from a genuinely clean clone with no homelab-specific knowledge assumed; clearly separates required vs. optional env vars and states what degrades gracefully without each optional one (Kev/Jev, Signal, eBay token, proxies).
- [ ] A short "what's configured on Michi's deployment specifically" doc kept separate from the general README, so the public repo stays generic while the real deployment notes still exist somewhere for you.
- [ ] LICENSE present and correct given any AGPL-derived code if you ever pull in pieces of AI Marketplace Monitor or similar — confirm licensing compatibility if you borrow from it, don't just copy silently.

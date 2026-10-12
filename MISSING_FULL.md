# MISSING_FULL — what DealRadar still lacks vs all user requests (2026-10-12)

Source: initial 61751-char spec + 20 follow-up requests (Dumped from `ai-used-product-finder-and-comparer.json`: benchmark-coverage complaint, DeepSeek-40tok/s rig hunt, EVO-X2/Framework/V100 discussion, 512GB requirement, mini-PC Merkliste negotiation, Firebat vs UM870, X1-Lite/1080Ti, willhaben/kleinanzeigen chats, AliExpress+China-warehouses+1881, laptop-mainboard cheat-code, chrome-debug-browser/temp-mail proposal).
Code ref: `/home/michi/hider/projects/deal-radar`, `AGENTS.md`, `ACCEPTANCE.md` (claims 40/40), `BLOCKERS.md`, `DECISIONS.md`, `PROGRESS.md`.

ACCEPTANCE says done. Real DB says otherwise: 18149 rows/14d, recent 500 sample title+desc CPU hit only 4.4%, `gems.py:40` counts clothes/bags as "without benchmark". This file is the honest delta. Next agent: do not stop until every box below is checked live or moved to BLOCKERS with 3 tried approaches.

## 0. Logic bugs proven live today (fix first)

- [ ] `packages/deal_radar/gems.py:40` uses `extract_cpu(title+desc)` only — ignores `MODEL_CPU_SEED` family estimates, bare-Intel inference, Xeon, AI-rig extraction. Result: `ThinkPad X1 Carbon Gen 6 / Yoga Gen 6 / T14s / E14 i3 10th / Legion Y520 i7` all counted unrated though seeds exist (`scoring.py:24-58,112`). Fix: Gems `collect()` must use same pipeline as enrich (exact > seed-estimate > fuzzy > unknown), and report `rated / seed-estimated / truly-unknown / non-system` separately.
- [ ] Denominator is wrong: `gems.py:66-79` counts every listing (Nike shorts, Sketchers, bags) as "without benchmark". Add `kind` split: systems-only unrated vs non-systems excluded. Show both numbers in `web-v2/src/views/GemsView.vue`.
- [ ] `packages/deal_radar/scoring.py`: `CPU_DB size 10`, `STATIC_DB` in `benchmarks.py:17-21` has 11 entries. `closest_known_cpu` cutoff 0.75 too strict, only searches static+disk cache. Expand static DB to ≥500 real PassMark entries (capture once, commit as fixture) or drop the function.
- [ ] `benchmarks.py:225-253` strict `_title_matches` refuses fuzzy endpoint results → `None`, caller treats as unknown forever, no retry via `closest_known_cpu`, no internet-research fallback. Log refused titles; fall back to closest-known + mark confidence low instead of silent unknown.
- [ ] `data/benchmarks.json` has 112 keys vs 18k listings — warmup only warms distinct recent CPUs (`DECISIONS.md:261`). No background backfill job. Add polite backfill worker (1 req/s, persistent cache next to DB — already done — but actually run it).
- [ ] Vinted titles embed marketplace metadata (`Marke:/Modell:/Zustand:`) and have empty `description` (no detail API). Extractor chokes on `X1 Carbon - Pari al nuovo, Marke:..., 200.0`. Fix: strip `, Marke:.*$` suffix before extraction; add vinted detail fetch or mark `detail:unsupported` honestly in Store.
- [ ] New Intel naming missed: `X1 Carbon Gen 14 - Ultra X7` — no pattern for `Ultra X7/X9` (`scoring.py:372-377` needs `X[579]` bare form). `X1 Extreme G4 RTX 3080` extracts GPU but no CPU — needs board-level fallback (see §2).
- [ ] Bare `i5`/`i7` with Gen hint (`Gen 6 ... i5`) never resolves. Combine signals: `seed(Gen)+tier(i5)` → estimate range instead of unknown.

## 1. Benchmark / recognition — "recognize EVERY item, miss no gems"

- [ ] OCR from images is tesseract-only, never runs in Gems path; serials/chassis stickers/model plates in photos unused. Wire: detail images → OCR → `extract_cpu/gpu` re-run; store `ocr_texts` for vinted/willhaben (currently empty for vinted).
- [ ] Vision `does image match description` exists (`vision.py`, cloud VLM) but VLM backend flaky (BLOCKERS: local VL stalled, TokenHarbor trio text-only, OrcaRouter `glm-5.3-flash-free` unproven at scale). Prove live pair test again uncongested; bench failures; honest `% + why + counter-evidence` in drawer for every vision run.
- [ ] No GPU/RAM/SSD/ports extraction in Gems ranking. User asked "check literally everything ram ssd ports cpu gpu". Add `extract_ram/ssd/ports` + sort keys + Gems columns; mini-PC compare must show CPU+MT/ST+iGPU+RAM(included?/barebone cost +85€/16GB rule)+SSD+USB4/OCuLink/WiFi7.
- [ ] Laptop-mainboard cheat-code: no board→CPU table, no soldered-CPU inference, no BIOS-whitelist/TDP note. Add `board_cpu_map` + DiyPerks-style flag (`mainboard:true`, socket, included cooler/RAM?) + risk note.
- [ ] Stage A is heuristic, not Kev/Jev (`README.md:25`, `decision.py`). "Blazing fast AI on every listing" untrue. Either route Stage A through Kev/CLI when healthy (bench latency) or correct README/ACCEPTANCE claim.

## 2. Markets / drivers — "search everywhere, new+used, any currency"

- [ ] AliExpress + China warehouses + 1688/1881/taobao: no driver (BLOCKERS: affiliate-API approval wall). User proposed: 3rd-party API, chrome-debug-browser/CDP, user-supplied account/temp-mail. Missing: generic CDP/authenticated-session transport + account-cookie driver template + `docs/DRIVER_AUTHORING.md` CDP chapter. Try 3 approaches each, log in BLOCKERS, build behind interface with clean error until creds.
- [ ] Non-used markets (Amazon PA-API, Alternate/NBB/Cyberport/Mindfactory/idealo/Geizhals partner-only): same — no code, only BLOCKERS text. Need per-site honest probe (1 polite request each, save fixture) + `needs: <exact approval clicks>` in Store, same pattern as Allegro/eBay.
- [ ] eBay still dead without creds (`drivers/ebay/driver.py`, BLOCKERS: needs exemption clicks). No tokenless fallback (refused: decoy cards — correct, but then eBay must be excluded from defaults + counts, and FX normalization dead code (`DECISIONS.md:290`) must be wired once eBay/Allegro return).
- [ ] Allegro.pl shipped mocked, needs `ALLEGRO_CLIENT_ID/SECRET` live proof (BLOCKERS). Do the one live search once creds land.
- [ ] Shpock keyword wall (`?q=` ignored → generic dump guard raises), no pagination (first page only), price-band slicing only an IDEA (`IDEAS.md:3`). Implement slicing probes (2-3 polite) or keep honest first-page label in tile (currently "source note" only).
- [ ] Ricardo 403, vinted 403s come-and-go, willhaben laptop-IP ConnectError-walled (BLOCKERS). No automatic transport failover per failure (proxy failover proven once via tunnel, not automatic). Add per-failure auto-rotate transport + `retry_at` already exists — wire rotation, not just cooldown message.
- [ ] Shopify driver exists but unused for AliExpress-type shops; no laptop-mainboard shop driver; no Geizhals-price-anchor driver (new-price baseline for used-vs-new compare missing).

## 3. Proxy / auth / anti-bot — "interchangeable, tries next thing on its own"

- [ ] `TRANSPORTS_JSON` supports direct/proxy/rotating but per-driver proxy picker in UI unverified; no health-check table per proxy; no auto-failover on 403/captcha (only manual proof). Prove: kill primary mid-search → secondary completes, evidence in tile.
- [ ] No CDP/chrome-debug transport, no cookie/account injection UI (user offered AliExpress account). Add `SESSION_COOKIES_JSON` + Store fields + SSRF/secret hygiene (never log values).
- [ ] Captcha/block detection is string-match only; no per-driver `automation_permission` enforcement in UI (manifest has it, Store doesn't surface ToS warning per driver — DECISIONS says public index accepted, but UI must show personal-use notice per install).

## 4. AI / scam / filters — "checks everything, configurable, never loses good deals"

- [ ] Scam `% + why + counter-evidence` exists but calibration unproven (evidence: "2 ordinary listings score 0.0" — weak). Need scored eval on ≥50 real listings (mix scam/bait/good), rescue-lane proof that high-value+high-risk stays in review, hard-filter threshold UX (100=off) already done — re-prove live.
- [ ] NL "real model, never regex": 10/10 proven on TokenHarbor (dead key) — re-prove on OrcaRouter uncongested (`scripts/nl-evidence.py` rerun off-peak, PROGRESS pending). List-keywords + blacklist-op coercion bugs fixed — regression-test.
- [ ] Junk war incomplete: cooler/RAM-stick/box demotion + bundle guard + 5x value cap exist, but user still saw yoga-mats/dresses/comics for "iphone 17" (AGENTS B). Re-run iPhone-17 page-1 eval (8/10 real claimed — re-prove).
- [ ] Location/delivery: distance calc + radius + dist sort exist, but `max_distance` post-fill enforcement + unknown-location counting ("46 without location hidden") need live re-proof; willhaben `areaId` + kleinanzeigen geo exist, vinted geo unverified.

## 5. Live / watches / favs / notifications — "always live, track everything"

- [ ] Watch-firing + tracking-timeline need natural listing changes (PROGRESS pending: loops proven operating, no natural-change evidence). Leave running watch on a live volatile listing until a real price/drop event notifies via ntfy+webhook+Signal; save payloads.
- [ ] Signal broken (`/v1/accounts=[]`, BLOCKERS: needs re-register). Email never sent (needs SMTP). Telegram dropped. No PWA push. Cross-platform favs = single password, no per-device sync proof. Prove: fav on browser A → visible on fresh profile B (screenshot), history timeline with price/desc/image diffs.
- [ ] SSE `/stream` latency + reconnect-after-drop unmeasured. Measure and log (ms from poll-detect to UI card).
- [ ] Stopped/interrupted never "done" done; pause TTL 6h; kill-9 drill done — re-prove after Vue-only cutover (journeys rewritten, need green run incl. sid-collision fix).

## 6. Lab / marketplace / in-app AI — "type plain words, get driver/enricher, PR it"

- [ ] Lab builds enricher from sentence + sandbox + hot-load proven (charger-missing demo, 0 FP/40, recall unmeasured). Missing: driver-from-sentence live proof (add 8th driver via Lab this session), GPU-enricher Lab proof already claimed — re-prove, failure visibility (build/test/site-blocked) in `LabView.vue` verified by forcing 3 failures.
- [ ] Auto-PR publish untested (needs `GH_TOKEN+LAB_PUBLISH=1`, BLOCKERS). Open real PR to test repo, link it.
- [ ] Remote plugin index: `marketplace/index.json` versioned — verify public URL fetchable from clean clone; Store install/uninstall incl. core roundtrip re-prove (was shpock cycle).
- [ ] User's endgame: "AI on the website directly exactly like this chat" — no conversational deal advisor. Missing: `POST /advise` chat UI (negotiation price, Firebat-vs-UM870-style compare, total-cost math) over current search/favs/Gems context. Gems `advise=1` summary exists but not chat.

## 7. Deal-hunt specifics still open (real-world requests)

- [ ] DeepSeek-40tok/s rig: physics + build sheet done in chat (dual-7302+512GB DDR4+2×3090 ~4k€), but no in-app `ai-rig` hunt pack proof with FX-normalized total-cost (base + shipping/travel/redirection) columns. `GPU_SPECS` tok/s ceiling exists; add `total_cost` (price+shipping+travel input) + sort, prove on live Allegro/eBay-once-creds + reachable markets.
- [ ] Mini-PC negotiation advisor: user haggled 7 listings manually. No `bargain predictor` (offer → accept-probability → walk-away price). Add per-listing `suggest_offer` (median-anchored + seller-age + days-listed) or document as wont-build in IDEAS.
- [ ] Full-spec mini-PC compare (RAM/SSD/ports/CPU/GPU) + barebone-hidden-cost rule (+85€/16GB, SSD owned) only in chat, not in CompareView. Wire into compare table.
- [ ] Unified-512 under 6k verdict ("does not exist") needs live re-check once new markets unlock (M3U-512, 4×Halo, DGX-2 prices change). Schedule re-hunt post-AliExpress/CDP.

## 8. Frontend / ops / tests — "test every feature real-world"

- [ ] Journeys: `scripts/journeys.sh` + `verify.sh` must both exit 0 vs prod AND local (AGENTS). Pending: NL 10/10 off-peak, Lab e2e uncongested, prod-UI edge needs LAN/test-user (BLOCKERS), clean-clone quickstart by a stranger (README claims it — actually do it in /tmp).
- [ ] Metrics: `/metrics` + admin panel diverge across restarts (in-memory vs SQLite, BLOCKERS). Derive from SQLite or persist events; add Prometheus/Grafana doc (user asked "advanced metrics full insight").
- [ ] Live tests in `tests/live/` excluded from CI — run them all gently now (benchmark, proxy, modelcheck, CLI, vision, vinted/willhaben categories) and paste outputs; rotate temp keys after (BLOCKERS: TokenHarbor temp, app-host password).
- [ ] Secrets hygiene: `grep -r REDACTED_` empty, history purge verified (369 Michi4-only) — re-verify after new commits; `.env` gitignored; no values in screenshots/logs.

## Do-not-stop order for next agent

1. Fix §0 first (Gems pipeline + denominator + static DB + vinted title strip + Ultra-X pattern). Re-run 500-sample probe: title+desc+seed hit rate + systems-only unrated count. Commit `fix:`.
2. Take next unchecked box, write test first, implement, `./scripts/verify.sh` green, live-prove (real HTTP/SSE/browser), commit `feat:/fix:` as Michi4, push, watch CI.
3. Externally blocked → 3 different approaches tried, logged in BLOCKERS with exact clicks/keys needed, code behind interface with working fallback, move on. Never end turn with text only (AGENTS.md).
4. Update PROGRESS.md every 5 steps; keep ACCEPTANCE evidence lines with command+observed output in THIS session.

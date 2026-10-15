# MISSING_FULL — what DealRadar still lacks vs all user requests (2026-10-12)

Source: initial 61751-char spec + 20 follow-up requests (Dumped from `ai-used-product-finder-and-comparer.json`: benchmark-coverage complaint, DeepSeek-40tok/s rig hunt, EVO-X2/Framework/V100 discussion, 512GB requirement, mini-PC Merkliste negotiation, Firebat vs UM870, X1-Lite/1080Ti, willhaben/kleinanzeigen chats, AliExpress+China-warehouses+1881, laptop-mainboard cheat-code, chrome-debug-browser/temp-mail proposal).
Code ref: `/home/michi/hider/projects/deal-radar`, `AGENTS.md`, `ACCEPTANCE.md` (claims 40/40), `BLOCKERS.md`, `DECISIONS.md`, `PROGRESS.md`.

ACCEPTANCE says done. Real DB says otherwise: 18149 rows/14d, recent 500 sample title+desc CPU hit only 4.4%, `gems.py:40` counts clothes/bags as "without benchmark". This file is the honest delta. Next agent: do not stop until every box below is checked live or moved to BLOCKERS with 3 tried approaches.

## 0. Logic bugs proven live today (fix first)

STATUS 2026-10-12 (commits a885d53/1afd709, verify GREEN 221 passed): 6/8 fixed, 2 open (static-DB expansion, refused-title fallback).

- [x] `packages/deal_radar/gems.py:40` uses `extract_cpu(title+desc)` only — FIXED: `collect_full()` + split counts — ignores `MODEL_CPU_SEED` family estimates, bare-Intel inference, Xeon, AI-rig extraction. Result: `ThinkPad X1 Carbon Gen 6 / Yoga Gen 6 / T14s / E14 i3 10th / Legion Y520 i7` all counted unrated though seeds exist (`scoring.py:24-58,112`). Fix: Gems `collect()` must use same pipeline as enrich (exact > seed-estimate > fuzzy > unknown), and report `rated / seed-estimated / truly-unknown / non-system` separately.
- [x] Denominator is wrong — FIXED: `unrated_systems` vs `unrated_nonsystem` + rated/estimated (Nike shorts, Sketchers, bags) as "without benchmark". Add `kind` split: systems-only unrated vs non-systems excluded. Show both numbers in `web-v2/src/views/GemsView.vue`.
- [ ] `packages/deal_radar/scoring.py`: `CPU_DB size 10`, `STATIC_DB` in `benchmarks.py:17-21` has 11 entries. `closest_known_cpu` cutoff 0.75 too strict, only searches static+disk cache. Expand static DB to ≥500 real PassMark entries (capture once, commit as fixture) or drop the function.
- [ ] `benchmarks.py:225-253` strict `_title_matches` refuses fuzzy endpoint results → `None`, caller treats as unknown forever, no retry via `closest_known_cpu`, no internet-research fallback. Log refused titles; fall back to closest-known + mark confidence low instead of silent unknown.
- [ ] `data/benchmarks.json` has 112 keys vs 18k listings — warmup only warms distinct recent CPUs (`DECISIONS.md:261`). No background backfill worker — OPEN (cache persists; worker queued) (1 req/s, persistent cache next to DB — already done — but actually run it).
- [x] Vinted titles embed marketplace metadata (`Marke:/Modell:/Zustand:`) and have empty `description` (no detail API). Extractor choked — FIXED: strip keeps `Modell:` `, Marke:.*$` suffix before extraction; add vinted detail fetch or mark `detail:unsupported` honestly in Store.
- [x] New Intel naming missed: `X1 Carbon Gen 14 - Ultra X7` — no pattern for `Ultra X7/X9` (`scoring.py:372-377` needs `X[579]` bare form — FIXED incl. `X7 358H` full form; X1-Extreme/Legion seeds added) (see §2).
- [x] Bare `i5`/`i7` with Gen hint (`Gen 6 ... i5`) never resolved — FIXED via tier-narrowed seeds.

## STATUS 2026-10-13 — first real hunt (3 live searches, scratch DB, fixed code)
Hunt-1 `ryzen mini pc` (50 res) + mainboard hunt (40 res, willhaben worked!) + 8745hs hunt (35 res).
Bugs found live + fixed: Ryzen tier-adjacent parse (SER5 5800H was "800H"); closest-fallback
now gated at 85% with labeled confidence (UM870 8745H no longer 5800H@0.97 — no exact page,
8745HS@0.867 is the correct stand-in); shpock per-item keyword gate (Fahrrad junk out);
gems ppe_full = complete-system cost (barebone +85 RAM/+40 SSD).
Cheat-code confirmed: 5700U board €32, 5500U board €24, X13/T14s 4650U board €90.
eBay verdict (manual — item+search pages 403 from here, 2 approaches tried): the €360 H255
NEW 16/512 stands as best complete deal (79.8 pts/€); only used-barebone UM870 (€340 all-in,
83.8) and ES/budget plays beat it on paper. Coupon POWEREBAY10 ends Oct 14.
CORRECTION 2026-10-13: minisforum refurbished ghosts — UM560 E139/UM690 E289
variants are SOLD OUT (avail False); shopify driver now buyable-only (sold-out
variants never price, dead products vanish). Available refurbished: UM760 Slim
7640HS barebone E239, UM880 PLUS 8845HS barebone E359, BD775i SE 7745HX board E279.
Best complete deal stands: eBay H255 NEW 16/512 E360 (79.8).
ROUND 3 (2026-10-13 eve): 7 more hunts (x270/x280, macbook boards, AM4 combos,
framework, xeon boards, pi5, defekt donors). Fixed live: seed brand-context
(carpets got i5-6200U banaus), bare-CPU completion (+150 tray), ghost purge.
Mini-PC donors: MS-01 13900H homeserver E658, UM880 Plus 8845HS 16/500 E479 (59.7).
Server boards: ML350 dual 2667V3 E200, E5-1660V3 chip E30, E3-1240V6 chip E15.
ROUND 4 (high-end boards): NO Halo/7945HX/Ultra/M4/Genoa boards on used market
(Framework 16 tax E999 only; Genoa query hits football shirts — query-side).
Desktop chips: 8700F+cooler E145 (104), 13600KF E210 (103), 12600KF E145 (93).
Cooler-trap fixed: >500 bench-per-euro flags review (E20 14400F FAN, not chip).
M3 Air headless E420 desktop-donor noted. Old hunt server retired (8099),
canonical hunt server 8090 runs all current code.
DEPLOYED 2026-10-13: Frankfurt (130.61.104.107) pulled to 870f36e, rebuilt,
dealradar-api healthy with 12 drivers incl ebay-web (ebay-web degrades loudly
there until session/cookies land; prod edge behind Authelia+app login, 401 as
designed). New-AI finds: M5 Max Studio E2725 (amazon.de, 64GB trap), no refurb
Studios on Apple AT right now.
ROUND 14 (no-mogger + AI reframe): 3090s sit E1399-1500 (solo can't hold Flash
weights — but a single 3090 does 40+ tok/s on 32B distills; reframe offered).
M1-Pro-14 defect trio on eBay: no-display E215 (item 117252189906), cracked+locked
E320 (298732574863), spare Grade-D E335+. T480 parts konvolut E10. No crown-taker;
asymmetry plays documented.
ROUND 13 (homeserver bang-buck): M75q-G2 5600GE complete E350 (51.5, 35W) is THE
repurpose gem; M75q-G1 3400GE E139 (55.8); B100 N100 E120 (idle king ~8W);
1235U boards E112+ (63 eff, eBay board chest); NUC8 E140 (55.6); MS-01 12950HX/48GB
E480 stays virtualization king. ebay-web proven top board source.
ROUND 12 (EVO-X2 + homeserver): EVO-X2/128 verified E3299.99 (256GB/s shared).
2x = E6.6k/256GB pools MEMORY, not speed (~10-20 tok/s — pipeline gives no
single-stream speedup). M1U-128 E5.3k stays 3x faster (800GB/s, 45-80 tok/s).
512GB fully: nothing under E10k (M3U-512 E11k). Homeserver: MS-01 12950HX/48GB
E480, 12600H bare E300, ECC 32GB E80+, HBA330 E60, CSE-836 16-bay E650, QNAP
10GbE E309. 64GB EVO (E2.xk) is a trap (Q3 needs ~120GB).
ROUND 11 (AI-rig 40 tok/s): floor is M1 Ultra 128GB — eBay E5295+20 ship (Bonn, DE,
item 940005703473) beats local E6500 OVP. M2U-128/4TB E6599 stretch, M2U-192 E8490
dream. 64GB boxes (E2680-4899) are TRAPS (weights don't fit V4.1-Flash). DGX/Halo
miss 40 (bandwidth). A100 PCIe absent (SXM4 only). RAM-heavy: 64GB SODIMM kits
E539-600, UM790-32 E550, MLLSE-24 E350.
ROUND 10 (mog-or-die): bulk lots (9x Optiplex E140, PC-Konvolut E100 — contents
unknown), capped-200 completes, US eBay spot-check (M75q auctions die on $93
ship; K12 H255 bare E250+125=75.6 loses to coupon). willhaben/KA flared bot-walls
under burst load — cooldown, no hammering. VERDICT: no living mogger; edges are
restock watches, ending auctions (AS5 Sat), negotiation (UM790-32 E500, AMR5 E140,
Legion-3070Ti diagnosis). ~50 hunts banked.
ROUND 9 (mog hunt): 40+ hunts total, zero crown-takers. Closest: P1/11800H+T1200
board E79, UM690 refurb E289 (SOLD OUT — watch recipe below), 9600X chip E140,
M1-Pro-14 defekt E549 (31.9, repair gamble only). New chip learned: 8940HX (~49k).
eBay auctions: nothing ending cheap (Firebat E318 same as vinted).
WATCH RECIPES (user creates in UI): minisforum source "UM690 refurbished" (restock
E289), "UM560 refurbished" (restock E199), vinted "AMR5" (price drop <140).
ROUND 8 (ultra/AI boards): only ONE Ultra laptop board exists used (Shuttle
DN11H+185H E509, weak value). No Halo/AI300/Ultra-laptop/M4/Genoa boards.
Real Ultra/AI value = desktop chips: 225 E150, 7900X E199, 7800X3D E270, 9600X
E140. Fixed: ultra suffix whitelist (225SERIA).
ROUND 7 (agent CLI + mega board sweep): scripts/hunt.py ships (one-command
multi-query hunts, markdown/JSON gems). 12-query sweep dogfooded. New gems:
3700X+board E120 (82.9), 9700K+16GB E160 (70), 9600X chip E140 (103 complete),
12100F E60 (66), X299+7820X E250. Fixed: accessory veto (keyboards/fans get no
estimates), resolution-as-CPU, part nouns, same-gen closest gate, 400-threshold
review flag. verify.sh GREEN (240 passed, 86%).
ROUND 6 (20k+ shootout): MLLSE 7840HS/24/1TB E350 (80.6, verified 1TB+USB4+box)
BEATS eBay H255 E360 (79.8) on perf-per-euro; eBay keeps new+warranty crown.
New: AM18 16/512 E450 (62.7), UM790Pro 32/1TB E550 (54.0, strongest sub-600),
UM780 XTX E466 (spec unverified), TA95X3D board E759 (62129 MT raw king, worst eff).
UM690Pro E359 = barebone (complete E484). No Halo/Ultra/M4/Genoa silicon on market.
ROUND 5 (apple/defect): M1 Air donors E180-320, M2 16/512 donor E490, Mini M1 E250,
M3 Air 16/256 E650 floor. Fixed live: resolution-as-CPU (2560X monitor), part
nouns carry no bench, closest-match same-generation gate (1600/2600/5500 honest
miss now), >500 bench-per-euro review flag (cooler trap). 165 tests green. Budget king: AMR5
offer E140 (128). Board kings: P1G4 11800H+T1200 E79 (98 eff), X13 board E75 (63.6),
5700U board E32 (~101 eff). UM560 refurb 16/512 E199 complete (71.8) IF restocked.

## STATUS 2026-10-12 II (verify GREEN, 86%, CI-tracked)
DONE: GemsView split counts + est. badges; frequency warmup (live: 25 fetches -> 831 rankable from 0);
full-spec extraction (ram_gb/storage/ports/barebone) on every enriched listing + Compare rows;
deterministic offer_targets enrichment + Drawer line (advise reuses formula).
OPEN: static-DB expansion; refused-title fallback; CDP/session transport for walled markets;
conversational advise chat; alternate.de driver (needs owner OK); prod journeys re-run;
NL 10/10 off-peak rerun; watch natural-change proof; Signal re-register + SMTP creds;
Lab auto-PR (GH_TOKEN); eBay exemption + Allegro creds (human clicks).

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

## Round 15 — scoring cleanup: junk-veto + naming-grade unification (2026-10-13)
Root-caused 4 junk classes that topped the board and killed them:
- compat clauses ("für/for/pour") now strip MODEL-FAMILY words but PRESERVE exact
  CPU tokens (cooler "für Ryzen 7 8845HS" is benched then implausible-flagged,
  never silently dropped). Stop set widened to [.\n] only so long compat lists
  ("für (WWAN configs): EliteBook 735 G6, 745 G5; ProBook 430 G8 ...") are eaten whole.
- used-with/narration clauses ("zusammen mit", "kühlte", "war eingebaut in")
  strip ENTIRELY (exact tokens too) — the CPU is context, not the item.
- HARD_PART_NOUNS + display/lcd/bildschirm compounds; accessory-head veto now only
  drops WEAK (<0.85) hints.
- NEW hyphen-Intel branch: i5-1240P / i7-1165G7 / i9-13900HX were falling to the
  0.45 generic loop; now 0.85 "mentioned" (G7-style letter+digit suffixes fixed).
- gems.board demotes implausible (bench/€ > 400) to the tail — flag, never hide.
Verified: 253 tests green, ruff+mypy clean. Board top is now all real systems
(LTE modem + AIO cooler + ideapad-3-fr false-positive expelled); rated 1025→1100.

## Round 16 — blocked sources unlocked via debug browser + mainboard hunt (2026-10-14)
Chrome CDP (localhost:9222, eBay profile with live session) now drives ALL three
previously-walled sources directly. New tooling in `scripts/browser_hunt/` (cdp.py,
batch_ebay.py, scrape_ka.py, scrape_wh.py, combine.py + README with the gotchas).
- 5 eBay batches (~50 queries, ~1,900 cards), kleinanzeigen 5 queries (100 cards),
  willhaben 8 queries with scroll-to-load (8 -> 33+ each). 847 offers scored
  through deal-radar's own resolve+PassMark pipeline.
- **NEW CROWN for laptop mainboards: Lenovo IdeaPad 5 14IAL7 mainboard,
  i5-1235U + 16GB RAM — €30** (willhaben, PayLivery, verified live on the item
  page). ppe 413 — 1.7x the previous best (X13 Yoga i5-1145G7 @ €24 = 381).
- Other modern-chip finds: Dell Vostro 3530 i7-1355U €71 (ppe 196, verified
  live), Dell Inspiron 5400 i5-1035G1 €28 (258), Dell Precision 7530 i7-8850H
  €54 (187), ThinkPad X13 Gen 3 i5-1235U 8GB €75 (165), Dell 3571 i7-12700H
  €232 (24,925 multi — highest modern board under €250).
- Standing king P1 Gen 4 i7-11800H+T1200 €79 still live (ppe 95.9 w/ uplift).
- Fixes while parsing: Intel 4-digit gen heuristic (i5-1235U is 12th-gen, not
  10th), willhaben `€ 30` euro-first price form, kleinanzeigen counter-badge
  anchor vs title anchor.

## Round 17 — full sweep: broken-screen-usable + complete minis (2026-10-14)
- 3 more eBay batches (brk1/brk2/mini1, ~30 queries), KA batch ka3 (6 queries),
  WH batch wh2 (5 queries). Total pool now 1,267 clean + broken-display pass.
- combine2.py: broken-display-usable lane (display/bildschirm/screen + complete
  system, dead-board signals excluded: no-power, mainboard-defekt, parts-only).
- Best broken-usable (headless homeserver): Dell Latitude 5300 i5-8265U cracked
  LCD €57 (ppe 101), Acer Swift SF314-42 R7-4700U ohne Display €181, IdeaPad Flex 5
  R5-4500U cracked €134, ProBook 440 G8 i5-1135G7 line-on-screen €178, Yoga C640
  i5-10210U cracked €101, Spin 5 i7-1065G7 display-dead €250, XPS 13 9310
  i7-1165G7 €271. POWER-DEAD units explicitly excluded (not usable).
- Best complete minis: Firebat H255 bare €285 (ppe 100), Gem12 Pro Max 8845HS
  homeserver €333, EM780 7840U/32GB €300, H255/16GB/512GB NEU €400, Geekom A7
  7940HS/32GB/2TB €390, AM18 7840HS/16/512 OVP €450, UM790 Pro 7940HS/32/1TB
  €550, EQR5 5825U/16/500 €349, AM08 Pro 7730U/32/1TB €399.
- Standing crowns re-verified live: IdeaPad 5 i5-1235U/16GB €30 WH (PayLivery),
  Vostro i7-1355U €71 / Precision 7530 i7-8850H €54 / Inspiron 5400 i5-1035G1
  €28 eBay (all gone:false, prices via .x-price-primary in USD ~0.90 EUR).

## Round 18 — AI 256GB+ ladder (2026-10-14)
20 eBay AI queries (1,142 cards) + KA/WH high-RAM sweep. Findings:
- Single-box 256GB unified exists exactly once: M3 Ultra 256GB/2TB €8,200 WH
  (1053100579). Only box that is BOTH ≥256GB AND 40-tok/s-class.
- M1 Ultra 128GB/2TB €4,600 WH Fischamend (1329708543, verified live
  gone:false) — new cheapest 128GB Ultra, beats Bonn €5,315. M3 Ultra 128GB
  €5,100 w/ AppleCare (1143292912).
- EVO-X2 128GB price UP: GMKtec 128GB/2TB now €5,804 eBay (406967941449) vs
  €3,299.99 earlier → 2x pooled-256GB now ~€11.6k, no longer sub-7k.
- DGX Spark 128GB cheapest ASUS Ascent GX10 €6,243 (157654794658) → 2x ~€12.5k.
- Cheapest 256GB-capable (CPU inference, slow): EPYC 7282+H12SSL-i from €1,527
  (377466613823) + 256GB DDR4 RDIMM ~€464 (325154460749) = ~€2k total;
  2x EPYC 7302+256GB+H11DSI €3,000 VB KA; EPYC 7551P 32C+256GB+HL15 €2,999 VB;
  2x EPYC 7532+256GB+2TB+18TB workstation €4,500 KA Halle (64C/128T).
- A100 80GB used still €10.7k+, RTX 6000 Ada 48GB €7.1k+ — dead ends.
- Verdict: no box is ≥256GB AND 40 tok/s under €7k. Ladder: ~€2k EPYC-256
  (5-10 tok/s) → €4.6k M1U-128 (fast, half capacity) → €8.2k M3U-256 (both).

## Round 19 — AI 512GB ladder (2026-10-14)
10 eBay queries + WH sweep. Findings:
- NO single-box 512GB-unified Apple on the used market (eBay 0 hits, WH 0 hits
  — only storage-512 false positives). New M3 Ultra 512GB CTO is ~€10-11k.
- Cheapest 512GB-capable: Supermicro 2HE 24-bay + 2x Xeon E5-2690v4 + 512GB
  DDR4 €3,036 eBay (137232153914, 28C/56T); modern pick Supermicro 2x EPYC 7452
  + 512GB/1TB from €3,482 (397978307775, 64C/128T, 8ch DDR4-3200).
- DIY RAM alone is worse: cheapest 512GB DDR4 kit new €2,485 (32x16GB-2133);
  8x64GB-3200 3DS €3,933 — always buy the complete server, never the kit.
- WH: HPE DL385 2x EPYC 7742 + 512GB €11,900 (128C total, overkill);
  ASUS RS700A dual-7763 €6,300 (bare, no RAM stated).
- Verdict: 512GB = EPYC-server territory €3-3.5k at ~8-12 tok/s CPU inference.
  512GB + 40 tok/s does not exist under ~€10k (M3 Ultra 512GB new).

## Round 20 — 4-tier verdict, Q4-floor rule (2026-10-14)
User: no cap, 4 tiers (best / reasonable-best / reasonable-overall / cheapest-fast),
speed first, NO retard quants (Q4 floor, Q6+ preferred). GPU floor sweep (6 queries):
- RTX 3060 12GB cheapest Dell OEM €317 (920027963459); RX 6700 XT 12GB €279
  (377461352474, weaker llama.cpp backend — NVIDIA preferred).
- Tesla P40 24GB real card €245 (389221097025) — 24GB for €245, Pascal, ~250W,
  needs 8-pin+cooling; 2x = 48GB @ ~€500, fits 70B Q4 split.
- RTX 3090 24GB cheapest Palit JP €1,326 (198677345234), MSI Trio €1,597.
- 4060 Ti 16GB €758+ — dead value vs 3090.
KEY CONSEQUENCE of Q4-floor: full Flash Q4 ~160GB+ctx does NOT fit 128GB boxes
at any sane quant → M1U-128/M3U-128 are OUT for full Flash (32B distills only).
Tiers: (1) M3U-512 new ~€10.5k CTO — only 512GB+fast box on earth; (2) M3U-256
used €8,200 WH — Flash Q6 fits, fast; (3) dual-7532+256GB €4,500 KA Halle —
Flash Q6 fits, 8-12 tok/s, doubles as homeserver; (4) 3060-12GB €317 box
~€500 all-in (14B Q6 fast) / 3090 €1,326 step-up (32B Q4-Q5 fast).

## Round 21 — cheapest VRAM/€, GDDR6+ floor (2026-10-15)
20 eBay GPU queries. GDDR5 excluded per user (min GDDR6, better welcome).
Coolers/fans/adapters/cables/defective filtered; MXM-laptop modules excluded.
Verified live (gone:false): P100-16GB €103, 6700XT-12GB €272, RTX8000-48GB €1696.
- Absolute: Tesla P100 16GB HBM2 €103 = 6.4 €/GB (Pascal/server/no display).
- Desktop plug&play: RX 6700 XT 12GB €272 = 22.7 €/GB; RTX 3060 12GB €301 = 25.1.
- Big single card: Quadro RTX 8000 48GB €1,696 = 35.3 €/GB (fits 70B Q5).
- Traps: €94 "P100" listing is a choose-one multi-GPU ad (cheapest option = P4 8GB);
  €355 3080Ti-FE "AS-I" = as-is gamble; A770 €267 hit was the 8GB version.

## Round 22 — app learns from real-world use (2026-10-15)
User: "nur ebay", Versand vergessen, "use doch dealradar". Fixes IN the app:
- ebay-web driver now maps card shipping into CanonicalListing.shipping_cost
  (it sat in attributes only -> total_cost() saw None -> every ranking ignored
  freight; a $567-freight 3090 ranked "cheapest").
- gems board ranks ALL-IN (item + shipping): new row fields ship/total, ppe_full
  over full_eur incl freight. Regression test proves the $100-freight trap loses.
- decision accessory: GPU cooling/parts ungated (lüfter/fan/heatsink/wasserblock/
  waterblock/backplate/nvlink/riser/bracket/stütze) — 21 junk cards ("0.9 €/GB
  kings") were fans/coolers. Stock-cooler BUNDLES ("ryzen + wraith", "+") stay
  offers via new _cooler_stems bundle guard (code comment promised it, code did
  not do it). Naming-grade cooler mentions still bench+flag (Noctua contract kept).
- NEW is_option_ad() (>=3 distinct GPU models -> price = cheapest option's,
  demoted like parts, never hidden) + gpu_vram_gb() via extended GPU_SPECS
  (3060/6700xt/6800/6900xt/vii/mi50/t4/arc770/a4000/a5000/rtx8000/a40 added).
- cond 0.25 now also for for-parts/as-is/untested/ungeprüft/sold-as.
- browser_hunt: WH euro-FIRST price bug fixed (model numbers parsed as prices:
  "Zotac RTX 3090 € 1.300" -> 3090, "Radeon VII € 300" -> 2); verify_items.py
  added (item-page price+shipping+strict sold detection). Its own postmortems
  fixed: USD comma decimals ($115,89 -> 10430), truncated shipnum shadowing,
  bare "verkauft"/"reserviert" matching nav/footer/similar-ads.
Verified: 258 tests green, ruff+mypy clean. All-in truth: P100 €149 (9.3/GB),
RX 6800 €403 free-ship (25.2/GB, best desktop), 3060 €321 (26.8), 6700XT €363
($100 ship flips it), 3090-Turbo €1,762 ($567 ship trap), WH local 3060 €270 /
6700XT €275 / Radeon VII €300 (live, "funktioniert einwandfrei") win.

## Round 23 — Strix Halo sweep: 8060S + 8050S, every platform (2026-10-15)
20 eBay queries + 4 dealradar-server searches (10 drivers each) + WH 6 + KA 5.
Server results carried the round (correct prices, lanes): cheapest 8060S = Flow
Z13 395+ 32GB/2TB €1,900 KA (verified live) / 32GB/1TB €1,999 (verified live);
GPD WIN 5 395+ 64GB/2TB €1,950 (verified live); EVO-X2 128GB/2TB €3,199 KA
(verified live, vs eBay €5,826); ZBook Ultra G1a PRO 395 64GB/1TB €2,450
(verified live); KI-Workstation 395 64GB €2,200 WH; MS-S1 Max 128GB €3,699;
Corsair WS300 128GB €4,000 WH; 128GB Halo box €4,999; ZBook 128GB €3,900;
Flow Z13 2025 128GB/2TB €3,300; eBay new-import: Flow Z13 390 (8050S) 32GB
€1,523, 395+ 64GB €2,508, ZBook PRO 385 (8050S) 32GB neuwertig €1,703,
OneXPlayer Super X 395 €2,670, X13-2025 395/128GB €4,470, ZBook 395/128GB/4TB
€8,165 (expensive gem: 4TB). 8050S completes: Framework Desktop 385 32GB/2TB
€1,650 KA (verified live); 385 board NEW + Noctua €999 (verified live).
BUG (mine, fixed): KA thousand-tail prices ("3.299 €" -> "299 €") in scrape_ka
+ item regex — same class as WH round-21. App eu_price was already correct.
Expensive-but-gems: ZBook 128GB/4TB €8,165 new, Kojima Z13-KJP 128GB €5,378,
GPD Win 5 Max 128GB €4,400, Halo 128GB/2TB box €4,999, Corsair €4,000.

## Round 24 — iGPU-only under 1k/1.5k (no dGPUs) (2026-10-15)
User correction: ONLY integrated graphics (dGPU round was wrong direction).
3 dealradar-server searches (enrich+benchmarks, 10 drivers) + eBay 6 + WH 5 + KA 5.
Server lanes carried it again (top/good): EliteBook 835 G10 7840U/32GB €600 KA
(verified live, Neu!), Pavilion Plus 14 7840U/1TB €690 WH, Elitebook 865 G10
PRO 7840U/32GB €700 KA, Envy x360 8840HS €650-700, IdeaPad Slim3 8840HS €799,
Zenbook 14 8840HS €800, Nitro Blaze 7 handheld 8840HS €500 WH (not deleted),
MacBook Air M4 13" €900 WH (page live, price in title), Air 15 M4 €1.000-1.100,
GEEKOM A9 Max HX370/32GB/1TB €850 WH, Vivobook 16 Flip 258V/32GB/1TB/OLED
€645 eBay, LG gram 17 258V/32GB €842 eBay (ohne Ladegerät), XMG EVO 14 HX370/
32GB/2TB €1.370 KA. Perf note: 8050S ~= RTX 4050 mobile -> used 4050/3060
laptops are the same class at €600-800 (deferred, user: later).

## Round 25 — Ask-box understands iGPUs + igpu hunt pack (2026-10-15)
User: everything here must work standalone on dealradar.home.websters.at (type a
sentence, AI does everything, filter after, one-click AI-picks).
- NEW IGPU_TABLE (scoring.py): 8060S/8050S/B390/890M/140V/880M/780M with chips,
  device match-tokens and ready device queries; expand_igpu_query() maps the iGPU
  name listings never use to the chips/devices they do use.
- nl_fallback() detects iGPU intents offline: keywords -> first device query,
  models = chips + device tokens (model gate passes BOTH "Flow Z13" and
  "Max+ 395"), subqueries = ready device queries, igpu label kept.
- /searches/nl fans out over subqueries (not bare "395" tokens) with bounded
  model gate. PROVEN LIVE: "anything with 8060S" -> 16 real results (EVO-X2
  128GB €3.150 KA new low! Flow Z13 395+, MS-S1 Max, rack mounts...).
- NEW /hunt pack "igpu" (halo / 890M+lunar / 780M class) + Gems "start igpu hunt"
  button next to value hunt; dist rebuilt+committed.
- Rack mounts ranked TOP at €49 -> mount/rackmount/einbaurahmen now accessories.
- GPU_SPECS: 3060/3070/4060ti/4070super/3080ti/6700xt/6800/6900xt/vii/mi50/t4/
  arc770/a4000/a5000/rtx8000/a40 vram+bw added (round-21 cards were unmapped).
Verified: 260 tests green, ruff+mypy clean.

## Round 26 — frontend consistency pass + iGPU board (2026-10-15)
User: simpler but fully controllable, beautiful, consistent, PM-grade.
- ResultCard: human lane line (was "top · 0.72 · kleinanzeigen"), all-in total
  chip when shipping known, image placeholder, score floats to tooltip.
- SearchView: hero Ask bar (PM-style focus ring) + one-tap iGPU preset chips
  (8060S/8050S/890M/140V/780M) that fill + run NL.
- tokens: radius-14 cards with hover lift, skeleton shimmer, shared .chip,
  empty states. Zero emojis in web/ (grep clean), no raw debug dumps.
- Gems keeps "start igpu hunt" + AI summary (= AI-picks flow).
- journeys: layout audit GREEN; journey-smoke mini-pc times out IDENTICALLY on
  HEAD (sandbox drivers return nothing) -> BLOCKERS entry, not a regression.
- verify.sh GREEN (lint+typecheck+tests+web build+docker).
iGPU board: 8060S from €1.900 (Flow Z13 32GB/2TB, live) / €1.950 GPD WIN 5 64GB /
€1.999 Flow 32GB/1TB / EVO-X2 128GB €3.150 KA (new low via Ask-box!); 8050S:
GPD Win 5 385 32GB €1.500 KA, Flow 390 32GB €1.523 eBay, Framework 385 €1.650,
ZBook 385 €1.703; 890M: SER9 Pro 32GB €929 KA, A9 Max 32GB €850 WH, EVO 14 €1.370;
780M class from €500 (Blaze) / €600 (EliteBook 32GB).

## Round 27 — three real-world hunts + GPU ask-box (2026-10-15)
User tests: (1) 7900 XTX / >16GB VRAM for 27B-class @40tok/s, (2) cheapest laptop
w/ best GPU, (3) cheapest anything w/ best GPU (user ref: 4070 Ti S @ €385).
- Server (enrich+bench): XTX Nitro+ €400 KA live (!) / €850-950 cluster / €900 WH+
  vinted; 4070 Ti S Yeston €500 KA live / Zotac €799 / vinted €750-799; Strix 3090
  €1,099 KA live / €1,190+; eBay-China loses all-in everywhere (XTX €1,239+).
- expand_gpu_query() + nl_fallback wiring: exact dGPU aliases, über-X-GB-VRAM
  gates, "best graphics card" (+laptop) tier fan-out. All three test sentences
  now resolve offline with queries + model gates (unit-tested).
- Qwen3/Gemma-27B @40tok/s note: 27B Q4 ~17GB -> 20GB+ cards (XTX/3090/7900XT);
  16GB (4070 Ti S) only via Q3/offload — stated honestly in answer.
Verified: 261 tests green, ruff+mypy clean.

## Round 28 — ALL GPUs, full spectrum (2026-10-15)
User: don't restrict to 4070TiS, look at EVERYTHING. 30 eBay queries (~1.800
cards) + WH 8 + KA + 3 server searches (vinted/KA/WH live).
- Verified live: Zotac 4070 Ti S €400 KA (!!), 3080 Vision OC €349 KA (!!),
  4060 Palit €230 WH, 7800XT TUF €480 WH, 9070XT €650 WH, 3080 €400 WH.
- Local beats China everywhere all-in (shipping trap, round 21 rule holds).
- GPU_ALIASES += 5090/5080/5070ti/5070/5060ti/5060 (round-27 gap).
Verified: 261 tests green.

## Round 29 — XPS 13 9340 replacement at selling value (2026-10-15)
User: XPS 13 9340 (155H/Arc/16GB, bought €400 used, RAM at 94%) -> sell it,
buy better for the proceeds. OLED nice-to-have.
- Selling value: comps 9340/32GB €950 WH, 9340/64GB €1,399 KA/vinted ->
  16GB base ≈ €550-650 realistic (€400 buy was a steal).
- Replacements at proceeds: EliteBook 835 G10 7840U/32GB €600 KA Neu (live,
  round 24) = same money, 2x RAM; Yoga Slim 7x SD-X-Elite/32GB/1TB/3K-OLED
  €740 WH (live); T14 G4/32GB/Garantie €619 WH (live); Dragonfly G4
  i7-1365U/32GB €583 eBay; x360-1040-G8 i5/32GB €605 eBay; Spectre x360 15
  €699 WH; Zenbook 14 OLED AI7/32GB/2TB €1,050 WH (stretch gem); T14s G5
  Ultra7/32GB/Touch €890-999 WH.

## Round 29 — XPS 13 9340 replacement + RAM floor (2026-10-15)
User rig: 155H (24.433 MT live cpubenchmark, rank 804/6051), 16GB 94% full,
weak battery. Rules: 32GB+ target (16GB gems too), budget = resale (~€500-600:
XPS 9340 32GB €950 WH / 64GB €1.399 / bought €400), <=14", CPU >=24k + iGPU >=
Arc-155H, OLED nice-to-have.
- VERIFIED: EliteBook 835 G10 7840U/32GB/Neu €600 KA (the pick: 24.4k + 780M +
  32GB at resale+100); Elitebook 865 G10 PRO/32GB €700; Pavilion Plus €690;
  Envy x360 8840HS OLED 14" €770 (stretch OLED); 835 G10 32GB/1TB+Dock €990.
- DEAD: Zenbook OLED €500 (page removed).
- APP: hard.min_ram_gb filter (extract_ram, missing->pass) + nl_fallback parses
  "32gb ram"/"more ram" (RAM word REQUIRED: bare "512gb SSD" must not become a
  RAM floor). Ask "laptop with more ram" now filters. 262 tests green.

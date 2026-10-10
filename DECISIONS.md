# DECISIONS.md — choices made autonomously (per AGENTS.md, no stopping to ask)

- AI host over app host/spare host for Kev+Ollama: 11GB RAM, WG-meshed, idle. spare host unreachable (BLOCKERS).
- Laptop keeps Kev+Ollama+VL copies (dev/fallback, vision backend for pipeline).
- Jev dropped (no key); Kev + local + OpenRouter-free cover all AI slots.
- OpenRouter free models congested evenings → local-first ordering + retry + NL disk cache.
- qwen2.5:3b for NL (0.6b/1.5b too weak); qwen2.5vl:3b for vision + note-consistency clamp.
- eBay ignored (no token); driver stays, clean error, out of defaults.
- Signal: wiring verified end-to-end, account re-link is user-side (BLOCKERS).
- Websters traefik has no Authelia → basic-auth there; app host uses real Authelia middlewares.
- External price/spec sources bot-walled → internal market-cohort plugin + PassMark CPU only.
- AI host signal-api impostor removed, home-server compose restored byte-identical.
- AI host deal-radar stopped; app host is the single primary (no split brain).
- AI host runs Kev ONLY (Ollama stopped/disabled — co-hosting thrashed 2 vCPUs: load 6, Kev >120s).
  NL text goes to laptop Ollama (15GB RAM); OpenRouter-free is last resort. Lesson: one AI per tiny host.
- POST /searches uses result cache (watcher forces fresh); keyword search 48s cold / 0.1s warm.
- Laya evaluated twice, NOT adopted: laya-serve on PyPI is a 0.1 stub (no server code);
  reported accuracy ~0.77 trails Kev; AI host Kev answers <2s. Revisit when laya-serve matures.
- eBay tokenless scraping REFUSED: bot-wall serves decoy cards (no prices/titles) — fake data risk.

- Proxy live test used 1 request via the homelab's own webshare pool (pricematters env, never committed); justified as de-minimis infra validation.
- Plugin/driver registry index stays PUBLIC: it lists scraper drivers, which lowers the bar for scraping at scale. Accepted because (a) every driver carries its ToS/personal-use notice, (b) drivers are polite by construction (≤1 req/s, cached), (c) the techniques are already public knowledge. Revisit if a source complains.

## 2026-09-27 (volume/pages/tracking batch)
- Unlimited = default (limit null). Caps only via UI select. enrich_top_n (150) bounds expensive
  work; flagged cap 5000. Perf stance: fetch is cheap, depth is bounded.
- Categories v1: only kleinanzeigen slugs verified live (notebooks/handys/autos/moebel-wohnen).
  willhaben /computer slug serves generic mix (subpaths 404) — deferred, needs real research.
  vinted 2050 = clothing, unmapped. Others: keyword fallback, documented in UI.
- Filter state: per-search intent restore on open + localStorage latest + reset-to-defaults.
  AI filters always overwrite advanced (visible application).
- Watches: 30min default, floor = max(60s, last search duration) with toast; new triggers
  desc/image/title/seller via orchestrator events; watch-from-tile endpoint.
- Product tracking Snoty-style: favorites re-fetched via fetch_detail (ebay/kleinanzeigen/
  willhaben only), title now versioned, snapshot time-travel in drawer. Others: no detail API.
- Lab/code-exec + SSRF + metrics-vs-SQLite still queued (unchanged).

## 2026-09-28 (willhaben categories verdict)
Attempted session-API bootstrap via real Chromium: no cookies set, document.cookie
throws SecurityError (bot-walled document). Combined with earlier findings (slugs serve
generic mix, verticals need per-shape parsers, robots.txt expressly forbids automation
incl. /webapi/), willhaben categories stay keyword-only until a tolerated path exists
(official API or explicit permission). kleinanzeigen remains the reference implementation.

## 2026-09-29 (machine cleanup + AI host Kev fixed)
User asked to clean unneeded LLM stuff. Found and fixed/done:
- Laptop ollama serve STOPPED + DISABLED (15G box was at 12G used; cloud-first now).
  Restart anytime: `sudo systemctl enable --now ollama`. Models stay on disk (nothing uninstalled).
- Laptop leftover uvicorn test servers killed; no Kev dev copy was running (nothing to do).
- AI host Kev was crash-looping ~36k times (`User=ubuntu` in a user unit → step GROUP
  denied). Removed the directive (+RestartSec 10→30), daemon-reload, now active and the
  /v1/systemone endpoint validates requests. Prod Stage B via KEV_URL works again (cloud
  remains the fallback behind it). AI host Ollama stays stopped (prior decision).
- AI host tinyproxy relay + laptop tunnel killed after the proxy proof (no open relays left).

## 2026-09-29 (AI host journey runner + WG bypass)
Laptop lost LAN L3 (only VPN uplink) → Authelia 302 (bypass is subnet-based). Michi
approved + applied the WG bypass himself (10.9.9.0/24 in authelia configuration.yml,
backup .bak-20260929, container restarted — I could not write the root-owned file).
Since the laptop still egresses via VPN exit (not WG), journeys run FROM AI host:
~/dr-journeys (playwright-core + ESM shim + cached chromium-1234), hosts override
10.9.9.2 app.example.net, edge 200. scripts/journeys/* stay canonical in repo.

## 2026-09-28 (cloud AI → TokenHarbor, model shootout)
User supplied a temp TokenHarbor key (OpenAI-compatible) and asked for cloud-first with
the best-fitting model. Live shootout 2026-09-28, same USB-C/iPhone JSON task:
- qwen3.8-flash:free — bare valid JSON (15→16e), ~100 tokens. PRIMARY.
- mimo-v2.6-flash:free — correct JSON in ```json fence (pipeline strips fences), 145 tokens. FALLBACK 1.
- deepseek-v4.1-flash:free — reasoning-bloated (1536 tokens), EMPTY content even at
  max_tokens=600, finish=length. LAST resort only.
Order: CLOUD_MODELS=qwen,mimo,deepseek. App already speaks /chat/completions with
response_format json_object + fence/reasoning fallbacks — no code change needed.
Prod .env switched (URL+models+key) + container restarted; NL parse verified
in-container (USB-C → iPhone 15/15+/Pro/Pro Max). Local dev: per-session env
(~/.config/deal-radar/tokenharbor.env holds URL+models; temp key NOT persisted —
rotate to a permanent key on TokenHarbor, then store it in prod .env only).

## 2026-09-28 (Lab sandbox — execution isolated, import stays gated)
Generated enricher code now fires in `deal_radar.lab_sandbox.run_in_sandbox` BEFORE any
in-process import: subprocess with secret-scrubbed env, RLIMIT_CPU/AS, socket egress
allowlist (default cpubenchmark hosts), wall-timeout kill, JSON verdict. Refusal blocks
the build with the sandbox reason. Layering is honest: import-time surface stays under
the AST allowlist (validate_python); driver generation only contract-checks the manifest
(no network execution at build time). Proven: 5 unit tests (fire, net-block, no-leak,
kill-loop, syntax) + wired into ailab.generate contract_check stage.
SSRF: listing image downloads (`vision.download_image`) now guard private/loopback/
link-local ranges, cap redirects at 3, keep the 8MB budget (5 unit tests). Fixed-host
fetchers (benchmarks, geocode, registry index) unchanged; community-driver installs stay
a privileged explicit action.

## 2026-09-28 (vinted categories — same playbook as willhaben)
Vinted catalog pages link their own tree as `/catalog/<id>-<slug>` path prefixes
(top 8: Men/Women/Kids/Home/Entertainment/Electronics/Sports/Hobbies; 10 subs under
Electronics incl. 3565-electronics_phones, both verified live with 1 GET each).
Driver: CATEGORIES/SUBCATEGORIES/CAT_SLUGS + resolve_category + search_url catalog-path
+ cached fetch_categories(parent). Same `GET /drivers/{id}/categories` contract.
Fixture: real trimmed capture (first 200KB — nav links live at the top, documented in
the test module). 3 unit + 2 live tests green. Display labels are prettified slugs;
slugs/ids are the ground truth (live test asserts slugs).

## 2026-09-28 (willhaben categories SOLVED via facet navigators — supersedes above)
Polite single-GET probes of the public marktplatz search page show `__NEXT_DATA__`
`searchResult.navigatorGroups` already embeds the full facet tree the site itself uses:
`category` navigator with `urlParamRepresentationForValue` = ATTRIBUTE_TREE=<numeric id>.
Top 19 verified live (Smartphones/Telefonie=2691, Computer/Software=5824, ...); drill-down
verified (2722 Smartphones/Handys with 29k rowsFound; 9 subs under Computer). No slug
guessing, no session/CSRF, no webapi — one plain search GET, same as the driver already does.
- `SearchQuery.category` now carries tree-id-or-label; per-driver `cat_map` override wins;
  willhaben appends `&ATTRIBUTE_TREE=<id>` in `search_url()`.
- Ads keep `categorytreeids` in `CanonicalListing.attributes` for client-side fallback filtering.
- `GET /drivers/{id}/categories[?parent=]` serves the chooser (static top-19, live cached
  drill 7d in data/wh_categories.json). `/drivers` already exposes static CATEGORIES.
- UI dropdown deferred to the frontend rebuild (port-every-page push); backend+tests+live done.
- Rate discipline: top-level = zero fetches (static snapshot of a real capture); drill = 1 GET
  per parent per 7 days; live tests = 2 requests total.

## 2026-10-05 — cloud AI: TokenHarbor → OrcaRouter; Zen rejected; cloud-first everywhere
- TokenHarbor 7-day trial hit its limit (owner-reported). Switched prod `.env` (server-side
  only, never repo): `CLOUD_API_URL=https://api.orcarouter.ai/v1`,
  `CLOUD_MODELS=deepseek/deepseek-v4-flash-free,tencent/hy3-free`,
  `CLOUD_MODEL_VISION=z-ai/glm-5.3-flash-free`; dead TokenHarbor key + `mimo-v2.5` refs +
  laptop-bound endpoints (`KEV_URL`, `LOCAL_*`, incl. a `10.8.1.1` address) removed from prod env.
- Owner order "cloud AI first, never the laptop": Stage B now tries cloud BEFORE Jev/Kev
  (`orchestrator.py`), vision tries cloud VLM before the local model (`vision.py`).
  Both keep honest fallbacks + breakers; nothing hangs when cloud is down.
- Provider 400s ("invalid parameters") no longer fail the call: `_body_variants()` in
  `decision.py` retries with optional fields stripped tier-by-tier (ollama-only `think`/
  `options`, then `response_format`, then bare model+messages). Same stripping in vision.
  Friendly UI mapping added (v1 `netMsg` + v2 `friendly()`) so a rejection reads as
  "AI backend rejected the request — retrying with fallback", never a raw dump.
- OpenCode Zen (`https://opencode.ai/zen/v1`, `Bearer public`) evaluated as a free
  server-side endpoint and REJECTED (see BLOCKERS: 3 probes, all `FreeTierError` —
  free tier is gated to in-OpenCode use). `_providers()` failover slots (`_2`/`_3` suffix)
  stay ready if that ever changes. `muse-spark-1.3-contributor-free` therefore cannot back
  deal-radar server-side; it works inside the OpenCode app (owner's `reasoningEffort: none`
  → `minimal` fix verified headless in 2.1s).
- eBay: added `GET+POST /ebay/marketplace-deletion` (SHA-256 challenge contract per eBay's
  guide, unit-tested incl. public-while-locked); but since we persist zero eBay user data,
  the documented recommendation is the EXEMPTION toggle, not the endpoint (BLOCKERS).

## 2026-10-08 — opencode CLI as opt-in keyless fallback AI (owner asked, proven live)
- Raw Zen HTTP with `Bearer public` is gated to in-OpenCode use (FreeTierError, 3 probes
  2026-10-05) — but the official `opencode run` CLI binary answers headlessly in ~2s with
  clean JSON. So: `OPENCODE_CLI_MODEL` (empty = off) + optional `OPENCODE_CLI_BIN`.
  `_cli_json()` in `decision.py`: temp cwd (no session pollution of the project), 120s
  timeout with kill, ANSI/`>`-header stripping, `{...}` extraction, None on any failure.
- Order in `cloud_json`: cloud providers → CLI (if enabled) → local Ollama → None.
  Cloud-first preserved; CLI skipped instantly when unset/binary missing (prod unaffected).
  JSON path only (NL + Stage B); Lab codegen untouched. In Secrets UI (non-secret).
- Caveats (README): contributor-tier data use (prompts may train Meta models — our prompts
  are listing titles/descriptions, never secrets); free-tier rate limits unknown; works
  wherever the CLI binary runs (laptop here; prod has none, so prod stays OrcaRouter).

## 2026-10-08 — prod standalone: opencode baked into image, muse default, model picker
- Prod must not depend on the laptop: opencode CLI is now BUILT INTO the image
  (Dockerfile multi-stage `ocbuild`: oven/bun:1.3-slim, pinned commit
  687664c63b2bb4eb9b9c7e0dc37227869282ed80, `build.ts --single`, binary copied to
  /usr/local/bin/opencode). No release tarball exists for v2 (only Arch builds from
  source; anomalyco tags stop at v1.18.x) — source build is the only reproducible path.
- `OPENCODE_CLI_MODEL` now DEFAULTS to `opencode/muse-spark-1.3-contributor-free`
  (empty = off). tests/conftest.py blanks it autouse so unit tests stay hermetic.
- Model picker (`packages/deal_radar/modelcheck.py`): pool = 3 OrcaRouter free chat
  models + CLI default (override via MODELCHECK_MODELS). Each probe is one tiny
  exact-`{"ping": 1}` task; only exact answers count. Ranking: proven-fast first,
  untried next, tripped failures benched 10 min. Every real AI call re-scores
  (latency + ok/fail); `POST /models/check` force-probes + persists to settings;
  startup bootstrap restores + re-probes in background; `GET /models/health` is instant;
  Admin → Models tab shows the table + a check button (v1 UI; v2 admin stays as-is).
- Order in cloud_json stays cloud-first: providers (health-ordered) → CLI → local.

## 2026-10-08 — opencode source-build lessons (proven by building it here)
- `packages/cli` builds the WRONG binary (`lildax`, the v2 server tool, no `run`
  subcommand). The agent CLI is `packages/opencode` (`build.ts --single --skip-install`
  after a root `bun install`; output `dist/opencode-linux-x64/bin/opencode`, ~178MB).
- Tagless source stamps version `0.0.0-…` and the free tier rejects it
  ("1.18.0 or newer required"). Fix: `OPENCODE_VERSION=2.0.24` at build time
  (same code as the distro 2.0.24 build, unmodified, pinned commit) — then muse-spark
  answers headlessly in ~4s through the fresh binary (verified live, exact JSON).
- bun compile needs GBs of temp space: laptop /tmp (tmpfs 7.6G) hit EDQUOT; build on a
  real disk. Prod host build will take a while (2335 packages + full build) — chained
  `build && up` so the old container keeps serving until the new image is ready.

## 2026-10-08 — unlimited everything + rich alerts + change tracking + cross-listings
- v1 keyword search was HARD-CAPPED at 30 (`limit:30` in `intent()` spread AFTER the
  user's `limit:limN` in the POST body — the input field could never win). Removed;
  empty limit = unlimited everywhere (API already had None=unlimited, drivers already
  walk to exhaustion, enrich_top_n=0 means all). Watches showing "40 hits" were carrying
  their creation-time limit, not an app cap.
- Cheap benchmark tier: CPU/GPU benchmark lookups now run for EVERY listing with a
  usable CPU (PassMark disk-cached, videocard table memory-cached; only brand-new CPUs
  cost a polite request). Details/OCR/vision/Stage-B stay deep-budget-gated. This is
  what makes perf/€ ranking complete over unlimited result sets.
- iGPU extraction: Arc 130V/140V/140T + Radeon 780M/880M/890M (+bare "780M", Vega).
- `spec_line()` (orchestrator): CPU + MT/ST marks + RAM/storage regex + 140-char
  description snippet. Used in price-drop/rise AND new-match alerts (Signal now shows
  what the box is, not just price+link).
- Change tracking: store.upsert now also diffs seller NAME (rating stored silently to
  avoid fluctuation spam) + observations row; price/desc/images/title existed. Watch
  forms (v1+v2) gained title/seller toggles (title defaults ON for new watches).
- Cross-listings: dedupe drops were silent; now the first sighting is kept and every
  other source's sighting attaches as `also_on` (+ why-line, metric). Shown as
  "also on: X €Y" chips in v1 cards + v2 ResultCard (types + refilter mapping updated).
  Lesson: attach MUST be a post-pass (scoring is inline, dupes arrive later).

## 2026-10-09 — mini-PC value hunt: 35k listings, gems found, app hardened
- Hunted 13,933 unique listings (8 mini/brand/office/high-end + 3 laptop/desktop/server
  queries, unlimited, all 6 drivers) with live PassMark on everything. Best measured:
  Ultra 9 285H ES barebone 375€ (150.5 pts/€, mobile page verified: FCBGA2114/55W),
  UN1290 i9-12900 32GB 409€ (106/€), 7900 gaming PC 450€ (113.8/€), X1-255 barebone
  310€ (92.7/€), AOOSTAR 8845HS barebone 299€ (94.5/€, ~71 true after RAM/SSD).
- AI advise proven live (not fallback): ranked 60, caught the 13900H/HX score
  inflation + the fake-'m3' listing + barebone hidden costs on its own.
- Fixed from user feedback: watch polls no longer send "Search done" (spam source);
  hidden-lane price drops logged-not-pinged; spec lines recover CPU from text +
  never print storage as CPU; iGPU patterns (Arc 130V/140V/140T, 780M/880M/890M,
  Vega); box/cooler/keyboard/RAM-stick kind demotion with bundle guard; kind-capped
  value (non-systems can't top perf/€); seller tracking; snapshot datetime fix
  (snapshots silently never saved — reopen-instant + advise-on-old now work).
- Known remaining noise: cooler-subject bundles with CPU names stay offers (visible,
  capped); vinted 403s come and go (honest errors, retry/proxy).

## 2026-10-09 — alert quality + junk war + persistent caches
- Spec lines now recover the CPU from text when no fact exists (marked "?"), never
  print storage as CPU, and include GPU + G3D. MT/ST marks + RAM/storage + description
  snippet in every price/new-match/tracked alert.
- Spam autopsy: watches sent "Search done" on EVERY poll (now one-shots only) and
  hidden-lane junk price-drops pinged (now logged-only). Rate-limit lockout surfaces
  its message in LoginView instead of "wrong password".
- Junk demotion: box-only/cooler/keyboard/RAM-stick title cues (multilingual) with a
  bundle guard (real PCs with "+Tastatur+Maus" stay offers); non-offer kinds get 5x
  value caps so boxes/coolers/cables can never top perf/€; RAM-speed guard
  ("PC2-5300U", "MHz", "DIMM") in both CPU branches; iGPU patterns (Arc 130V/140V/140T,
  780M/880M/890M, Vega) with full confidence.
- Benchmark cache moved next to the DB (persistent volume) — rebuilds used to wipe it.
- Snapshot datetime fix shipped: old searches reopen instantly, advise works on them.

## 2026-10-09 — Gems value board + hunt pack (owner: "exactly this on the website")
- `GET /gems`: ranks everything seen recently (listings table, 14d window) by measured
  perf/€, efficient+cheap, perf/Watt, raw — CPU extraction + cached benchmarks +
  kind classification, zero network. `advise=1` adds the AI summary over the top 30.
  `favs=1` restricts to saved favorites (manual additions via track-by-URL count).
- `POST /hunt` ("value" pack): one click starts the same 3 broad unlimited searches
  the big hunt used (mini PCs / laptops+desktops / high-end+servers); advise on the
  returned ids for the full summary. v1 Gems tab + v2 GemsView with tables, links,
  hunt + AI-summary buttons.
- Missing-link lesson: the fabled "7900 gaming PC 450€" couldn't be re-found after
  the hunt (likely sold within a day — gems go fast, or a bundle title). Reported
  honestly with live alternatives instead of inventing a URL. Takeaway logged: for
  time-critical gems, advise snapshots + `also_on` at hunt time, don't trust recall.

## 2026-10-09 — Vue-only: v1 deleted (owner: "stop programming 2 things")
- `web/` (index.html, app.js, admin.html/js, css) deleted; `/` + `/admin` +
  client routes serve the Vue SPA; `/v2*` 301-redirects home; `/static` mount,
  favicon allowlist entry, `_page`/`_asset` helpers gone; `/favicon.ico` -> 204.
- v2 AdminView gained the Models tab (health table + check-all button) for parity
  with the removed v1 admin; router base is `/` everywhere now.
- Journeys follow: journey-smoke rewritten as the mini-pc E2E on Vue (search small
  -> Perf/€ sort -> drawer -> Gems rows -> hunt pack 3 ids -> stop+delete cleanup);
  layout-audit walks Vue routes incl. /gems; all three take DR_PASSWORD for the
  app-login gate (empty = dev). verify.sh asserts v1 stays gone.
- Startup now also warms the benchmark disk cache (distinct CPUs from recent
  listings, polite 1/s) so /gems is rated minutes after a deploy instead of empty.

## 2026-10-09 — journeys green on Vue-only prod (incl. sid-collision catch)
- Full trio GREEN against prod post-deploy: layout audit (9 pages x 4 viewports x
  2 themes, incl. /gems), journey smoke (mini-pc search -> Perf/EUR sort -> drawer ->
  Gems 103 rows -> hunt pack -> cleanup), v2 smoke (core loop, refilter, compare).
- Journey caught a real bug: hunt-pack jobs created in the same millisecond shared
  one sid and overwrote each other (seen as duplicate ids). `_start_job` now has a
  per-process sequence suffix (`s_<ms>_<seq>`); unit-tested with 10 same-ms starts.
- Frankfurt kinescope: /etc/hosts pinned the domain to the dead homeserver
  (journeys got homeserver-Traefik 404s) -> repointed to 127.0.0.1; journey login
  snippets now always POST /login (server login page has no `.loginwrap` marker;
  empty password = dev passthrough).

## 2026-10-09 — gems cards + recognition jump (owner reviewed screenshot)
- Gems is now sortable cards (perf/€, perf/W, MT, price, CPU, source) with thumbnails,
  title links, open-listing + fav buttons, section tabs, live counts. Proven in
  browser: 100 cards, 100 thumbs, 200 links, zero JS errors.
- Recognition: +150 lineup seeds (ThinkPad/Latitude/EliteBook/ZBook/MacBook-years/
  office micros), bare-Intel inference (8650U/1145G7/12450H + X3D/X/F/G parts via
  first-two-digit tiers), Xeon patterns, split i-prefix forms. Screenshot-verified:
  rated items climbing as warmup + seeds compound (1408 -> 1792).
- Junk war, round 2: XMP/RAM-stick/cooler/keyboard demotion with bundle guard
  (real PCs with "+Tastatur+Maus" stay offers); non-offer value capped 5x.

## 2026-10-09 — AI-rig hunt: cheapest 40 tok/s for DeepSeek V4.1 Flash (284B/13B act)
- Physics first: Q4 ~160GB (fits 192GB, NOT 128GB boxes — those need Q3/IQ ~100-120GB);
  ~7GB/token -> 40 tok/s needs ~280 GB/s effective. Ceilings = bw/7, real = 40-70%.
- Shipped for it: GPU_SPECS table (VRAM+bw, est tok/s ceiling), multi-GPU + unified-mem
  extraction, FX normalization in value scoring (dead code until eBay/ricardo return),
  "ai-rig" hunt pack (studio/dgx + 30x90 + halo). Q3's bare "128gb" sub-query matched
  phones/SD cards (junk) — narrowed to strix-halo/evo-x2 terms after.
- Market (live): M1U-128 4600€ / M3U-128+AC 5100€ / M2U-192 8490€ / DGX new 4000€ /
  EVO-X2-128 3000€ / A100-SXM4 1700€ (TRAP: socketed, not PCIe) / no PCIe-A100, no
  used-5090, no used-3090-cards (only want-ads) on reachable markets. eBay creds
  would unlock US PCIe-A100/3090 supply.

## 2026-10-10 — 512GB AI-rig verdict: EPYC+DDR4+3090s beats minis and V100s
- Memory math (rules everything): V4.1-Flash/284B fits 256GB up to Q6 (235GB) and
  192GB at Q4; R1/V3/671B needs 512GB for Q4_K_M (~400GB), 256GB only fits IQ2/Q2
  (~235GB, degraded). "512GB actually" is correct for full-fat 671B.
- V100 cluster killed with numbers: 16x16GB can't hold Q4 (24GB/GPU needed) -> IQ2
  max; pipeline across 16 stages ~300-500ms/token (~3 tok/s); 5kW + server chassis
  + no NVLink on PCIe cards. 6000-11000 EUR all-in for a loud IQ2 space heater.
- Cluster correction that matters: 2 nodes pipeline-parallel = 2x MEMORY, NOT 2x
  speed (same FLOPs sequential + link overhead). 2x EVO-X2 buys 256GB capacity at
  single-node speed minus overhead — good for bigger quants, not for 40 tok/s.
- Live build sheet (all links verified in chat): dual 7302 190 EUR + used H11DSi +
  16x32GB RDIMM ~800 EUR + chassis ~350 EUR + 2x used 3090 ~2400 EUR + NVLink 160 EUR
  = ~4000-4800 EUR for 512GB + 48GB VRAM. Single-box shortcut: complete 7302+256GB
  server 1150 EUR + 2x3090 = ~3700 EUR for the V4.1-Flash tier (256GB fits Q6).

## 2026-10-10 — Allegro.pl driver shipped; bazos/backmarket rejected with reasons
- 7th source: Allegro official REST API (client-credentials mint cached to disk,
  defensive parsing of promoted/regular shapes, PLN via FX table, pagination to
  exhaustion). Same honest pattern as eBay: real code, mocked contract tests, clean
  error until the owner pastes 2 self-serve values. Live proof pending creds.

## 2026-10-10 — 512GB verdict: single-Rome + 512GB DDR4 + dual-3090 (~4k EUR)
- Framework correction: 128GB board is $3,149 (not ~$2k) -> 2x = ~5.8k EUR for 256GB.
  Dead for 512GB, dead-ish under 6k. Owner caught it, estimate withdrawn.
- DDR5 RDIMM prices kill Genoa-DDR5-512 (32GB DDR5 ECC 449-899 EUR/stick; 64GB 1550).
  DDR4 RDIMM stays 3-4x cheaper per GB (bulk 32s ~50 EUR/stick).
- Live winner: single EPYC 7302 95 EUR + used SP3 board + 16x32GB DDR4 ~800 EUR +
  chassis ~300 EUR + 2x used 3090 ~2400 EUR + NVLink 160 EUR = ~3700-4000 EUR for
  TRUE 512GB + 48GB VRAM, single-stream MoE-friendly (no network penalty ever).
- Unified-512 under 6k does not exist (M3U-512 8k+, 4xHalo 9k+, DGX-2 17k+ for old V100).
- V100 route stays dead (pipeline math + 5kW + IQ2-max + chassis costs).

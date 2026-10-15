# BLOCKERS.md — external items this agent cannot clear alone. Everything else keeps moving.

- [x] Signal (verified live 2026-09-30): account registered, proof message sent
  (note-to-self, timestamp returned by the API). ntfy + webhook proven earlier.
- [ ] Email notifier: implemented + unit-tested, never sent a real message.
  Needed: SMTP host/user/pass + recipient, or say drop it like Telegram.
- Telegram dropped per owner (not needed).

- [ ] Prod-UI verification path (2026-09-28): laptop lost LAN L3 (wifi connected at L2 per
  nmcli with 192.0.2.172, but no kernel interface; default route is WG). All prod edge
  traffic egresses WG (src 10.9.9.12) → Authelia 302 (bypass only covers 192.0.2.0/24).
  Journeys (audit green + smoke 10/10) were proven against production BEFORE the route
  broke and now re-run vs local same-commit servers + in-container prod endpoint checks.
  Needed (pick one): (a) laptop back on LAN L3, (b) add 10.9.9.0/24 to Authelia LAN-bypass
  (your own mesh — your call, I won't touch security config unilaterally), or
  (c) a throwaway Authelia test user for playwright.
- [ ] Laptop IP willhaben-walled (2026-09-29): willhaben returns ConnectError from this
  laptop's egress after this session's probing volume (facets, categories, searches).
  Polite rule now: NO willhaben live fetches from the laptop; willhaben live proofs run
  from prod/app host IP or after a cooldown of days. Unit + fixture coverage stands in.
- [ ] Vision VLM backend missing (2026-09-29): local qwen2.5vl unusable (ollama startup
  stalls on Arc GPU probing + only 2.3G RAM free; service stopped again); TokenHarbor
  free trio is text-only (no vision model offered). vision_check code + breaker + honest
  {}-degradation are unit-covered; OCR (tesseract) proven live. Needed: a reachable VLM
  (cloud vision model or fixed local ollama) for the match/mismatch pair proof.

- [ ] TokenHarbor key is TEMPORARY (user-supplied 2026-09-28): lives in prod
  `~/docker/deal-radar/.env` (app host) + chat history only — never in repo/docs.
  Needed: permanent key → replace CLOUD_API_KEY in prod .env, then revoke the temp one.
  Key rotation hygiene: `grep -r REDACTED_` must stay empty across the repo (CI-greppable).

- [ ] OpenCode Zen free tier as server-side AI: REJECTED after 3 live probes (2026-10-05) —
  (1) `hy3-free` via /chat/completions → "Model hy3-free is not supported" (no such Zen ID);
  (2) `nemotron-3.5-lightning-free` via /chat/completions with Bearer public →
  `FreeTierError: OpenCode's free tier can only be used from within OpenCode`;
  (3) `mimo-v2.6-flash-free` same → same FreeTierError; muse-spark via /responses → same.
  The free tier is client-fingerprinted to the OpenCode app, not usable as a server-side
  endpoint. Needed: nothing — OrcaRouter free tier (user key in prod .env, never in repo)
  is the working cloud path, proven live 2026-10-05 (NL "iphone with usb c charging" →
  iPhone 15/16 models, 6/6 real USB-C phones). If OpenCode ever opens server-side free
  use, `_providers()` already supports a second failover provider via CLOUD_API_URL_2 etc.

## eBay HTML verdict 2026-10-13 (CORRECTED: headed+session WORKS)
- curl/curl_cffi/headless-shell, laptop AND Frankfurt: 403 Error Page (anonymous dead).
- Headed Chromium 151 + real user login: REAL results (60 cards, screenshot-matched).
  Page mixes 2 decoy placeholder slots (ebay.com/itm/123456, empty titles) into real
  ebay.at items — parser skips them (JUNK_TITLES + /itm/123456 filter, unit-tested).
- SHIPPED: drivers/ebay_web/ (session-web driver, CDP nav lock, title-verify retry),
  registered as builtin `ebay-web` (12 drivers live), fixture tests + live test green,
  proven end-to-end through the app pipeline (25/25 correct-query boards, full enrich).
  Needs EBAY_CDP_URL (debug Chrome, headed once for login; cookies persist in profile).
  Frankfurt run pending cookie/session refresh there — same pattern applies.

- [ ] eBay live proof: client-credentials mint implemented + unit-tested (mocked token + search),
  App ID/Cert ID fields in Secrets UI. Owner's keyset is DISABLED with the banner
  "Comply with marketplace deletion/account closure notification process or apply for
  an exemption" — nothing to mint against until that clears. FASTEST PATH (we store zero
  eBay user data — only public listing search): apply for the EXEMPTION, not the endpoint:
  developer.ebay.com → Application Keys → Alerts & Notifications → flip "Not persisting
  eBay data" ON → Confirm → pick the reason matching "public catalog search only" →
  Submit. Keyset activates, then: paste App ID + Cert ID in Admin -> Secrets, run one live
  search. (The `/ebay/marketplace-deletion` challenge endpoint is built + unit-tested and
  waiting for the day we ever DO persist eBay user data — `EBAY_VERIFY_TOKEN` (32-80 chars,
  alnum/`_`/`-`) + `EBAY_PUBLIC_URL` go in Admin -> Secrets; endpoint must stay publicly
  reachable, already bypassed in the auth gate.)
  No scraping, ever: public pages serve decoy cards to bots — scraping would inject FAKE
  listings, plus ToS bans bots. The official Browse API path is the compliant one.
- [ ] Shpock deep pagination (2026-09-28, 4 polite attempts, first-page SSR ~60 stands):
  (1) ?page=2/&offset=40/&o=40 all return page 1 (same itemSearch key, ~60 summaries);
  (2) results page chunk has no query doc; (3) 3 shared data chunks hold only the Apollo
  client lib; (4) build-manifest maps the results page to ~29 chunks — too many to pull
  politely. The itemSearch persisted-query hash + variable shape (pagination/od cursor)
  remain unknown. Needed: the persisted hash (from a real browser devtools capture by Michi:
  Network -> graphql -> extensions.persistedQuery.sha256Hash + variables) or official API
  access. Fallback active: first page + honest per-search status. Idea logged: price-band
  slicing per FINISH cap-workaround rule.
  UPDATE 2026-09-30: ?q= filtering is VOLATILE (generic dump one day, 61 real summaries
  the next); ?minPrice/?maxPrice verified inert (53/61 item overlap = unfiltered).
  No category links in markup (same persisted-query wall). Dump-guard stands.
- [x] AUTH (audit HIGH, 2026-09-27): simple password login shipped, live-verified.
  HttpOnly SameSite session cookie 30d, /login page + JSON, 5/min brute-force bucket,
  extendable to users/OTP later). Enabled on prod 2026-09-27 (password in server .env,
  handed to Michi in chat). Unit-tested + live-verified (401/303/cookie/429).
- [ ] spare host unreachable: old IP dead; not on WG mesh at .10–.22 (scanned 2026-09-30
  from AI host) and not on tailnet by that name. Needed: exact IP or hostname to verify
  + put to use. Fallback active: AI host runs Kev; cloud-first covers the rest.
- [x] eBay driver auth: client-credentials mint shipped 2026-09-28 (App ID + Cert ID in
  Secrets UI, auto token mint/cache/refresh, unit-tested; explicit EBAY_OAUTH_TOKEN kept as
  override; keyless scraping still refused — decoy cards). Live proof pending creds (see top).
- [ ] External enrichment sources bot-walled (probed 2026-09-25, single gentle requests each):
  videocardbenchmark 403/404, geekbench 403, gsmarena search Cloudflare-Turnstile, geizhals JS app-shell,
  heureka 403. Working: PassMark CPU detail pages. Needed: official APIs/keys or tolerated source.
- [ ] Signal account `+430000000000`: API up on app host, account data on disk, but `/v1/accounts` = `[]`
  and `/v2/send` → "account does not exist". All existing `notify_*.sh` scripts fail silently too
  (always `exit 0`). Needed: re-register/verify the number (phone/SMS) or re-link primary device.
  Wiring (app container → local signal-api port) verified working.
- [x] Jev: dropped, stays dropped (owner-confirmed 2026-09-30). Jev is only the Stage-B
  decider when JEV_API_KEY is set; Kev (fixed, on AI host) + cloud cover that path fully.


- [ ] Lab auto-PR publish: mechanism implemented (`lab_publish` via GitHub Contents+Pulls API) but untested — needs GH_TOKEN + LAB_PUBLISH=1. PR flow itself proven separately (PR #1 opened+merged via gh CLI). Needed: token to run one end-to-end publish.

- [ ] Telegram/email notifiers: implemented + unit-tested, never sent a real message. Needed: bot token+chat ID or SMTP creds for one live send each.

- [ ] New-market drivers evaluated 2026-10-10 (owner: search everywhere, incl. new):
  SHIPPED: Allegro.pl official-API driver (client-creds, self-serve, mocked tests green,
  clean-errors until creds). Needs: ALLEGRO_CLIENT_ID + ALLEGRO_CLIENT_SECRET
  (apps.developer.allegro.pl -> register app, read-only, NO approval wait) in
  Admin -> Secrets, then one live search to verify. Unlocks PL new+used supply (PLN,
  FX-normalized, ships to AT cheap).
  REJECTED (documented, no fake drivers): bazos(.sk/.cz/.at) — robots.txt disallows
  /search.php + all query params (polite scraping off the table); Back Market —
  product API is partner-only (no self-serve); Amazon PA-API (needs approved associate
  + sales); Geizhals/idealo (no API, JS-walled); leboncoin/marktplaats/subito
  (protected, no API); Wallapop (internal API only, ToS gray). eBay still needs YOUR
  exemption clicks (developer.ebay.com -> Keys -> Alerts & Notifications -> flip
  "Not persisting eBay data" ON -> Confirm -> reason "public catalog search only" ->
  Submit) — biggest remaining unlock (global new+used incl. US PCIe-A100/3090 supply).

- [ ] New-product markets (owner: cover non-used too, evaluated 2026-10-11):
  AliExpress: product data only via Affiliate API (Portals approval: account +
  traffic-source review, commission-based) — no anonymous search API, pages are
  Akamai-walled. Amazon: PA-API needs approved associate account + 3 qualifying
  sales/180d. Alternate/notebooksbilliger/cyberport/Mindfactory/idealo: no open
  product APIs at all. Geizhals: partner-only feed. NONE implementable without
  approvals — if you want any of them, tell me which account to wire and I build
  the driver the same day (same honest pattern as Allegro/eBay: real API code,
  mocked tests, clean-errors until keys land).

## New-product markets probe 2026-10-12

Method: exactly ONE polite GET per site (curl, timeout 15s, UA `hobbyist-research-probe/1.0`,
no auth, no redirect-follow, ~2s gap between hosts, total ~28s). Raw heads (headers + first
5KB body) saved under `/tmp/opencode/newmarket-probes/<site>.txt` — NOT in git, bodies never
committed. Static-data = title+price+product-URL present in the single response HTML.

| site | status | static-data? | what's needed (exact approval/account clicks) |
|---|---|---|---|
| aliexpress.com (`/wholesale?SearchText=thinkpad`) | 301 → `de.aliexpress.com/w/wholesale-thinkpad.html` (Tengine, `x-rule-name: AE_GLOBAL_UNLOGIN`) | NO — 63B redirect stub only | AliExpress Affiliate/Portals approval (account + traffic-source review) or user-supplied session cookies via future CDP transport; anonymous fetch is geo-redirect + Akamai-walled |
| 1688.com (`/`, homepage) | 200, 124KB Chinese homepage shell (`阿里1688首页`), zero `thinkpad` hits | NO (for queries) — homepage only, search is JS/app-shell (`window.__` x7), no `offer_search` SSR | 1688 seller/login session or approved 1688/Open-API app key; anonymous search URL not probed further (1-GET limit) |
| amazon.de (`/s?k=thinkpad`) | 200, ~1MB SSR | YES — 28x `data-asin="B0…"`, 88x `/dp/…` links, `€806.62`-style prices, 138x ThinkPad titles in static HTML | PA-API still needs approved associate account + 3 qualifying sales/180d for a compliant API driver; HTML scraping is ToS-gray (decoy/captcha risk) so no scraper driver without owner call |
| alternate.de (`/listing.xhtml?q=thinkpad`) | 200, 175KB SSR (Cloudflare `cf-cache-status: DYNAMIC`, no challenge) | YES — 24x `/product/<id>` links, 92x ThinkPad titles, `€ 799,00`-style `<span class="price">` in static HTML | No open product API exists; needs merchant feed agreement (Alternate partner contact) or explicit owner approval for polite HTML polling |
| notebooksbilliger.de (`/search?q=thinkpad`) | 403, 871B `bot detected` page (echoes client IP + UA, mailto `feedback.nbb.com` contact link) | NO — bot-walled | Delisting from their bot-protection (email the shown contact link from a real browser session) or official partner feed; no self-serve API |
| cyberport.de (`/tools/search-results.html?q=thinkpad`) | 403 Cloudflare challenge (`cf-mitigated: challenge`, `Just a moment…`) | NO — JS challenge shell | Clean-browser session with cleared challenge (manual) or Cloudflare-friendly partner feed; no self-serve API, no challenge-solving |
| mindfactory.de (`/search.php?search_query=thinkpad`) | 404 `File not found.` (Apache/Ubuntu, 16B) — this URL shape is dead | NO — wrong path, nothing to parse | Correct current search-URL shape (needs one careful browser check by Michi) + merchant terms; no open API |
| idealo.de (`/preisvergleich/MainSearchProductCategory.html?q=thinkpad`) | 403 Akamai block page (`server: AkamaiGHost`, `request_id`, `reference ID 0.d611702…`, "Something has gone wrong") | NO — bot-walled | Idealo partner/product-feed contract (idealo business onboarding); anonymous fetch is Akamai-walled |
| geizhals.at (`/?fs=thinkpad`) | 200, 288KB SSR despite `x-ua-device: bot` request label (Cloudflare DYNAMIC) | YES (unexpected) — 129x ThinkPad titles with specs, `€ 989`-style prices, SERP result markup in static HTML | Geizhals partner-only price feed for a compliant driver (https://geizhals.at/partner or Preisvergleich-partner onboarding); HTML is fetchable today but ToS/robots-gated, needs owner call before any polling driver |
| bazos.sk (`/search.php?hledat=thinkpad`) | 200, 50KB SSR (`Thinkpad bazár`) | YES (unexpected) — 40x `inzerat/…` links, ThinkPad titles, `350 €`-style prices in static HTML | robots.txt disallows `/search.php` + query params, so polite scraping stays OFF the table despite the 200; needs explicit owner exemption decision or official cooperation |
| backmarket.de (`/de-de/search?q=thinkpad`) | 301 → `/testchallengepage?next=…` (Cloudflare `__cf_bm`, 0B body) — bot challenge | NO — challenge-walled | Back Market partner product API (partner-only onboarding); no self-serve access |

Public `products.json`/feed endpoints discovered: NONE. No Shopify markers in any response
headers or bodies (all custom stacks: Tengine/Alibaba, CloudFront/Amazon, Cloudflare+custom
for Alternate/Cyberport/Geizhals/BackMarket, Akamai fronting idealo, nginx for bazos.sk).
Only incidental `/feed` substrings inside JS bundles (amazon, nbb) — not product endpoints.
Geizhals/idealo feeds are partner-only; no `products.json` anywhere.

## journey-smoke mini-pc E2E timeout (2026-10-15, round 26)
- `scripts/journeys.sh` journey-smoke waits 5 min for `.rgrid .res` results and
  times out. Reproduced identically on unmodified HEAD (`git stash` run) in this
  sandbox, so NOT a regression from the SearchView/ResultCard rebuild (layout
  audit is GREEN with the changes; `.modeseg`, `#searchbtn`, `.rgrid .res`
  selectors all still present).
- Likely cause: live drivers return zero usable results in this sandbox
  (kleinanzeigen/vinted blocked, willhaben throttled), so the result grid never
  fills. Needs: re-run against production Frankfurt where drivers are warmer,
  or a fixture-backed smoke mode. Human: run `BASE=https://dealradar.home.websters.at
  ./scripts/journeys.sh` from a warm network to confirm green.

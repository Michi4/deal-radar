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

- [ ] eBay live proof: client-credentials mint implemented + unit-tested (mocked token + search),
  App ID/Cert ID fields in Secrets UI. Owner's developer account is PENDING approval
  (≥1 business day) — nothing to mint against until eBay approves. Then: paste App ID +
  Cert ID in Admin -> Secrets, run one live search. (No scraping, ever: public pages serve
  decoy cards to bots — scraping would inject FAKE listings, plus ToS bans bots. The
  official Browse API path is the compliant one and it's ready.)
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

# BLOCKERS.md — external items this agent cannot clear alone. Everything else keeps moving.

- [ ] Prod-UI verification path (2026-09-28): laptop lost LAN L3 (wifi connected at L2 per
  nmcli with 192.0.2.172, but no kernel interface; default route is WG). All prod edge
  traffic egresses WG (src 10.9.9.12) → Authelia 302 (bypass only covers 192.0.2.0/24).
  Journeys (audit green + smoke 10/10) were proven against production BEFORE the route
  broke and now re-run vs local same-commit servers + in-container prod endpoint checks.
  Needed (pick one): (a) laptop back on LAN L3, (b) add 10.9.9.0/24 to Authelia LAN-bypass
  (your own mesh — your call, I won't touch security config unilaterally), or
  (c) a throwaway Authelia test user for playwright.

- [ ] TokenHarbor key is TEMPORARY (user-supplied 2026-09-28): lives in prod
  `~/docker/deal-radar/.env` (app host) + chat history only — never in repo/docs.
  Needed: permanent key → replace CLOUD_API_KEY in prod .env, then revoke the temp one.
  Key rotation hygiene: `grep -r REDACTED_` must stay empty across the repo (CI-greppable).

- [ ] eBay live proof: client-credentials mint implemented + unit-tested (mocked token + search),
  App ID/Cert ID fields in Secrets UI, but no real eBay developer credentials to mint against.
  Needed: EBAY_APP_ID + EBAY_CERT_ID (developer.ebay.com self-serve) pasted in Admin -> Secrets,
  then run live search once. (Old EBAY_OAUTH_TOKEN path kept as explicit override.)
- [ ] Shpock deep pagination (2026-09-28, 4 polite attempts, first-page SSR ~60 stands):
  (1) ?page=2/&offset=40/&o=40 all return page 1 (same itemSearch key, ~60 summaries);
  (2) results page chunk has no query doc; (3) 3 shared data chunks hold only the Apollo
  client lib; (4) build-manifest maps the results page to ~29 chunks — too many to pull
  politely. The itemSearch persisted-query hash + variable shape (pagination/od cursor)
  remain unknown. Needed: the persisted hash (from a real browser devtools capture by Michi:
  Network -> graphql -> extensions.persistedQuery.sha256Hash + variables) or official API
  access. Fallback active: first page + honest per-search status. Idea logged: price-band
  slicing per FINISH cap-workaround rule.
- [x] AUTH (audit HIGH, 2026-09-27): simple password login shipped (`LOGIN_PASSWORD`,
  HttpOnly SameSite session cookie 30d, /login page + JSON, 5/min brute-force bucket,
  extendable to users/OTP later). Enabled on prod 2026-09-27 (password in server .env,
  handed to Michi in chat). Unit-tested + live-verified (401/303/cookie/429).
- [ ] spare host (203.0.113.88) unreachable: `ubuntu` + `root` key auth both denied, no password known.
  Tried 2026-09-25 (ssh BatchMode). Needed: working user/key to use it for Kev/Ollama offload.
  Fallback active: AI host (11GB RAM) hosts Kev-0.8B + Ollama; laptop keeps dev copies.
- [x] eBay driver auth: client-credentials mint shipped 2026-09-28 (App ID + Cert ID in
  Secrets UI, auto token mint/cache/refresh, unit-tested; explicit EBAY_OAUTH_TOKEN kept as
  override; keyless scraping still refused — decoy cards). Live proof pending creds (see top).
- [ ] External enrichment sources bot-walled (probed 2026-09-25, single gentle requests each):
  videocardbenchmark 403/404, geekbench 403, gsmarena search Cloudflare-Turnstile, geizhals JS app-shell,
  heureka 403. Working: PassMark CPU detail pages. Needed: official APIs/keys or tolerated source.
- [ ] Signal account `+430000000000`: API up on app host, account data on disk, but `/v1/accounts` = `[]`
  and `/v2/send` → "account does not exist". All existing `notify_*.sh` scripts fail silently too
  (always `exit 0`). Needed: re-register/verify the number (phone/SMS) or re-link primary device.
  Wiring (container → `10.9.9.2:8082`) verified working.
- [ ] Jev key: user has none (dropped as requirement — Kev + local/cloud models cover it).
  Free $5 credit available at console.typesafe.ai if ever wanted.

- [ ] eBay without token: search pages return decoy template cards (fake IDs, $ prices on .de, 62 title tags all 'Shop on eBay'); item pages stripped (0 EUR prices, no h1) — both verified 2026-09-26 with TLS impersonation + session cookies. Scraping it would inject FAKE listings, refused per no-fake rule. Needed: free EBAY_OAUTH_TOKEN (developer.ebay.com self-serve); token driver ready and clean-errors until then.

- [ ] Lab auto-PR publish: mechanism implemented (`lab_publish` via GitHub Contents+Pulls API) but untested — needs GH_TOKEN + LAB_PUBLISH=1. PR flow itself proven separately (PR #1 opened+merged via gh CLI). Needed: token to run one end-to-end publish.

- [ ] Telegram/email notifiers: implemented + unit-tested, never sent a real message. Needed: bot token+chat ID or SMTP creds for one live send each.

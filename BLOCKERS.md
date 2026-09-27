# BLOCKERS.md — external items this agent cannot clear alone. Everything else keeps moving.

- [ ] AUTH TOPOLOGY DECISION (audit HIGH, 2026-09-27): API_KEY unset by default (incl. prod) →
  every endpoint open to anyone past the edge; no per-user isolation (searches/favs/watches
  readable+deletable by ID-guessing). Mitigations landed (rate limits, AST gate, checksums, CSP,
  headers) but don't replace auth. Options: (a) auto-generate+persist API_KEY on first boot
  [recommended], (b) accept Authelia-only + document fork risk, (c) per-user tokens + owner
  columns. Needed: Michi picks a/b/c. Prod-ready sign-off blocked on this.
- [ ] spare host (203.0.113.88) unreachable: `ubuntu` + `root` key auth both denied, no password known.
  Tried 2026-09-25 (ssh BatchMode). Needed: working user/key to use it for Kev/Ollama offload.
  Fallback active: AI host (11GB RAM) hosts Kev-0.8B + Ollama; laptop keeps dev copies.
- [ ] eBay driver: no `EBAY_OAUTH_TOKEN`. Driver implemented, reports clean error, excluded from default searches.
  Needed: eBay developer Browse API credentials to enable.
  (No-token scraping REFUSED on purpose: eBay serves decoy template cards to bots — verified
  2026-09-25 with TLS impersonation + cookies. Free self-serve token: developer.ebay.com.)
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

# BLOCKERS.md — external items this agent cannot clear alone. Everything else keeps moving.

- [ ] Mumbai (141.148.205.88) unreachable: `ubuntu` + `root` key auth both denied, no password known.
  Tried 2026-09-25 (ssh BatchMode). Needed: working user/key to use it for Kev/Ollama offload.
  Fallback active: Frankfurt (11GB RAM) hosts Kev-0.8B + Ollama; laptop keeps dev copies.
- [ ] eBay driver: no `EBAY_OAUTH_TOKEN`. Driver implemented, reports clean error, excluded from default searches.
  Needed: eBay developer Browse API credentials to enable.
  (No-token scraping REFUSED on purpose: eBay serves decoy template cards to bots — verified
  2026-09-25 with TLS impersonation + cookies. Free self-serve token: developer.ebay.com.)
- [ ] External enrichment sources bot-walled (probed 2026-09-25, single gentle requests each):
  videocardbenchmark 403/404, geekbench 403, gsmarena search Cloudflare-Turnstile, geizhals JS app-shell,
  heureka 403. Working: PassMark CPU detail pages. Needed: official APIs/keys or tolerated source.
- [ ] Signal account `+4367763177763`: API up on homeserver, account data on disk, but `/v1/accounts` = `[]`
  and `/v2/send` → "account does not exist". All existing `notify_*.sh` scripts fail silently too
  (always `exit 0`). Needed: re-register/verify the number (phone/SMS) or re-link primary device.
  Wiring (container → `10.8.1.2:8082`) verified working.
- [ ] Jev key: user has none (dropped as requirement — Kev + local/cloud models cover it).
  Free $5 credit available at console.typesafe.ai if ever wanted.

- [ ] eBay without token: search pages return decoy template cards (fake IDs, $ prices on .de, 62 title tags all 'Shop on eBay'); item pages stripped (0 EUR prices, no h1) — both verified 2026-09-26 with TLS impersonation + session cookies. Scraping it would inject FAKE listings, refused per no-fake rule. Needed: free EBAY_OAUTH_TOKEN (developer.ebay.com self-serve); token driver ready and clean-errors until then.

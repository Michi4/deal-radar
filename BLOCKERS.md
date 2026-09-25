# BLOCKERS.md — external items this agent cannot clear alone. Everything else keeps moving.

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

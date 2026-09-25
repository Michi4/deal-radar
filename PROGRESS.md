# PROGRESS.md — current state + next steps (fresh sessions start here)

## State (2026-09-25 ~05:30)
Live at https://dealradar.home.websters.at (Authelia; LAN-bypass per user config).
Brains: Frankfurt Kev-0.8B (systemd, :8001) + Ollama qwen2.5:3b (keepalive 24h, :11434);
laptop: Kev-0.8B (:8001) + Ollama qwen2.5:3b + qwen2.5vl:3b (vision backend for pipeline).
verify.sh GREEN, 26 pytest + Playwright E2E green, CI green.
NL search: local-first AI → per-model fan-out (iPhone 15/16 proof: 14 phones, 0 cables).
Watches/searches/favorites persist in sqlite; watcher re-polls after restart.
Details: willhaben (seller age, full desc) + kleinanzeigen (attrs, price, images) fetch_detail live.

## Next 5
1. README/docs accuracy pass (quickstart, env table, architecture, driver docs).
2. Frontend polish round (sort controls, lane filters, perf/€ sort using enrichments).
3. Opportunistic: free vision model via OpenRouter when uncongested; Mumbai when creds exist.
4. Notifications live test for telegram/email when user provides creds (ntfy+webhook proven).
5. eBay token / Signal SIM verify — user actions (BLOCKERS).

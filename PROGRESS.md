# PROGRESS.md — current state + next steps (fresh sessions start here)

## State (2026-09-25 ~04:30)
Live at https://dealradar.home.websters.at (Authelia; LAN-bypass per user config).
Brains: Frankfurt Kev-0.8B (systemd, :8001) + Ollama qwen2.5:3b (keepalive 24h, :11434);
laptop: Kev-0.8B (:8001) + Ollama qwen2.5:3b + qwen2.5vl:3b (vision backend for pipeline).
verify.sh GREEN, 25 pytest + Playwright E2E green, CI green.
NL search: local-first AI → per-model fan-out (iPhone 15/16 proof: 14 phones, 0 cables).
Watches/searches/favorites persist in sqlite; watcher re-polls after restart.
Willhaben fetch_detail live (seller age, full desc).

## Next 5
1. Kleinanzeigen fetch_detail (full desc, seller, attributes).
2. README/docs accuracy pass (quickstart, env table, architecture).
3. Frontend polish round (sort controls, lane filters, perf/€ sort using enrichments).
4. Notifications live test for telegram/email when user provides creds (ntfy+webhook proven).
5. Opportunistic: free vision model via OpenRouter when uncongested; Mumbai when creds exist.
See ACCEPTANCE.md for full checklist, BLOCKERS.md for external blocks, DECISIONS.md for choices.

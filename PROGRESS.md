# PROGRESS.md — current state + next steps (fresh sessions start here)

## State (2026-09-25 ~05:30)
Live at https://dealradar.home.websters.at. Keyword search 48s cold / 0.1s warm (cache);
watcher re-polls in background so watches stay fresh without waiting.
Brains: Frankfurt Kev-0.8B ONLY (Ollama removed — co-hosting thrashed the 2 vCPUs);
NL text → laptop Ollama; vision → laptop VL; OpenRouter-free last resort.
verify.sh GREEN, 27 pytest + Playwright E2E green, CI green.

## Next 5
1. Opportunistic: OpenRouter free vision when uncongested; Mumbai when creds exist.
2. Telegram/email live test when user provides creds; Signal needs SIM re-link (user).
3. eBay token (user) to enable third source.
4. More drivers via docs/DRIVER_AUTHORING.md (vinted/shpock candidates).
5. Frontend beauty round (currently functional vanilla; user offered Vue pick).
See ACCEPTANCE.md, BLOCKERS.md, DECISIONS.md.

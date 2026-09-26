# PROGRESS.md — 2026-09-26, end of autonomous session

## Verified state
- ACCEPTANCE: 73/76 checked with live evidence; 3 open = all BLOCKED with entries + working fallbacks
  (ebay-tokenless, lab auto-PR GH_TOKEN, Signal-alive + telegram/email creds).
- verify.sh GREEN (ruff+mypy+86% coverage, pinned CI versions), CI green, clean-clone pytest green.
- Prod (homeserver): 6 drivers live, marketplace remote index, Lab builds+fires, watcher autonomy proven,
  SSE live, backup cron ran, jump-host deploys working.
- Brains: Frankfurt Kev (<2s), laptop Ollama 3b + VL, OpenRouter last resort, breakers everywhere.

## Next (needs human)
1. EBAY_OAUTH_TOKEN, Signal SIM re-link, GH_TOKEN, telegram/email creds, Mumbai creds.
2. User eyes on the Tailwind UI (screenshots verified, taste is theirs).
3. OpenRouter-free vision when uncongested (local VL covers it when laptop awake).

## Standing notes
- NEVER push without local verify.sh GREEN (burned twice).
- Fixture HTML may contain third-party keys → scrub before commit (burned once, Mapbox).
- test mocks: bare `patch.object` (correct) vs `new=lambda` (breaks async ctx managers).
- NL disk cache is prompt-versioned; server volume persists it (stale-intent safe).
- One AI per tiny host (Frankfurt thrash lesson).

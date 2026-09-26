# PROGRESS.md — 2026-09-26, continued session

## Verified state
- ACCEPTANCE: all checked except 3 BLOCKED (ebay-tokenless, lab auto-PR GH_TOKEN, Signal-alive + telegram/email).
- verify.sh GREEN (ruff+mypy+86%), CI green, clean-clone green (58 passed).
- Prod: 6 drivers live, marketplace remote index, Lab builds+fires, watcher autonomy, SSE live,
  backup cron ran, jump-host deploys, total-cost DNA + sort, kind toggles, refine bar, searches dashboard.
- Brains: Frankfurt Kev (<2s), laptop Ollama 3b + VL, OpenRouter last resort, breakers everywhere.

## Next (needs human)
1. Signal receipt confirmation (2 test messages accepted with timestamps).
2. EBAY_OAUTH_TOKEN, GH_TOKEN, telegram/email creds, Mumbai creds.
3. Eyes on Tailwind UI.

## Standing notes (reaffirmed)
- No push without local verify.sh GREEN. Fixture HTML: scrub third-party keys before commit.
- Test mocks: bare patch.object (correct) vs new=lambda (breaks async ctx managers).
- NL cache is prompt-versioned; server volume persists it.
- One AI per tiny host. Reset --soft stages everything (commit in chunks deliberately).

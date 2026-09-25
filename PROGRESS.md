# PROGRESS.md — current state + next steps (fresh sessions start here)

## State (2026-09-25 ~03:00)
Live at https://dealradar.home.websters.at (Authelia; LAN-bypass per user config).
Brains: Frankfurt Kev-0.8B (systemd, :8001) + Ollama qwen2.5:3b (keepalive 24h, :11434);
laptop: Kev-0.8B (:8001) + Ollama qwen2.5:3b + qwen2.5vl:3b (vision backend for pipeline).
verify.sh GREEN, 19 pytest + Playwright E2E green, CI workflow exists.
NL search: local-first AI → model fan-out (iPhone 15/16 proof: 14 phones, 0 cables).

## Next 5
1. GPU/second enricher proving generic fabric (or document why blocked).
2. Transports: socks5/rotating proxy live failover test.
3. AI driver-authoring skill (`drivers/_template` + registry `install` exist; add generator command).
4. Notifications live test (Signal blocked on SIM re-link — user action; test ntfy/webhook live).
5. CI green confirmation + README/docs accuracy pass.
See ACCEPTANCE.md for full checklist, BLOCKERS.md for external blocks.

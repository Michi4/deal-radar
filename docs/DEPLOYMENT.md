# DEPLOYMENT.md — Michi's setup (not generic; README stays generic)

## Hosts
| host | role | access |
|---|---|---|
| app host 192.0.2.24 (`home`) | deal-radar app + signal-api + traefik/authelia | LAN SSH (`home`, pw) or AI host jump: `ssh ubuntu@203.0.113.107` → `/tmp/ff.sh "<cmd>"` (WG 10.9.9.2) |
| AI host 203.0.113.107 (`ubuntu`) | Kev-0.8B :8001 (systemd user unit, linger on), jump host | SSH key |
| laptop 192.0.2.172 | Ollama qwen2.5:3b :11434 + qwen2.5vl:3b (LAN bind), Kev-0.8B :8001 (nohup, dev) | local |
| spare host 203.0.113.88 | idle 11GB ARM — future AI offload (needs Tailscale/Headscale first) | `.ssh/termius/indiaServ.key` |

## App deploy (app host)
```
cd ~/docker/deal-radar/app && git pull && cd .. && docker compose up -d --build
```
- URL: https://app.example.net (Authelia; LAN bypass per authelia config)
- Data volume: `dealradar-data` (/data/dealradar.db + /data/lab-*). Backup: `~/bin/backup_dealradar.sh` (cron 03:17).
- Off-host copy: AI host `~/bin/pull_dealradar_backup.sh` (cron 04:05) pulls newest nightly
  over WG to `~/backups/dealradar/<date>/`, 14-day retention. Restore drill 2026-09-28:
  copied to /tmp, `integrity_check=ok`, tables readable (2 searches/60 results/19 jobs), cleaned.
- Server `.env` (never git): EBAY_OAUTH_TOKEN(empty), CLOUD_API_URL=https://tokenharbor.ai/v1,
  CLOUD_API_KEY=(temp TokenHarbor key, prod .env only), CLOUD_MODELS=qwen+mimo+deepseek free flashes,
  KEV_URL=http://10.9.9.1:8001/..., LOCAL_API_URL=http://192.0.2.172:11434/v1, SIGNAL_* (account unlinked), LAB_ENABLED=1, API_KEY unset (relies on Authelia).

## AI backends (order: local → TokenHarbor cloud free → heuristics)
- TokenHarbor (OpenAI-compatible) is the cloud backend since 2026-09-28: qwen3.8-flash primary
  (clean JSON, frugal), mimo-v2.6-flash fallback (fenced JSON), deepseek-v4.1-flash last
  (reasoning-bloated, empty content — verified live). See DECISIONS.md for the shootout.
- AI host Kev: `systemctl --user status kev` (must have `loginctl enable-linger ubuntu`).
- AI host Ollama: STOPPED/DISABLED on purpose (co-hosting thrashed 2 vCPUs — see DECISIONS.md).
- Laptop Ollama: systemd `ollama` service with `OLLAMA_HOST=0.0.0.0:11434` override.

## What degrades without what
- No laptop on LAN: NL falls back to TokenHarbor-free (congested evenings) → keyword fallback; vision checks skip fast (breaker).
- No AI host: Stage B skipped (heuristics stand).
- No cloud key: same as above, fully offline-capable.

# DEPLOYMENT.md — Michi's setup (not generic; README stays generic)

## Hosts
| host | role | access |
|---|---|---|
| homeserver 192.168.1.24 (`home`) | deal-radar app + signal-api + traefik/authelia | LAN SSH (`home`, pw) or Frankfurt jump: `ssh ubuntu@130.61.104.107` → `/tmp/ff.sh "<cmd>"` (WG 10.8.1.2) |
| Frankfurt 130.61.104.107 (`ubuntu`) | Kev-0.8B :8001 (systemd user unit, linger on), jump host | SSH key |
| laptop 192.168.1.172 | Ollama qwen2.5:3b :11434 + qwen2.5vl:3b (LAN bind), Kev-0.8B :8001 (nohup, dev) | local |
| Mumbai 141.148.205.88 | idle 11GB ARM — future AI offload (needs Tailscale/Headscale first) | `.ssh/termius/indiaServ.key` |

## App deploy (homeserver)
```
cd ~/docker/deal-radar/app && git pull && cd .. && docker compose up -d --build
```
- URL: https://dealradar.home.websters.at (Authelia; LAN bypass per authelia config)
- Data volume: `dealradar-data` (/data/dealradar.db + /data/lab-*). Backup: `~/bin/backup_dealradar.sh` (cron 03:17).
- Server `.env` (never git): EBAY_OAUTH_TOKEN(empty), CLOUD_API_KEY=openrouter, KEV_URL=http://10.8.1.1:8001/..., LOCAL_API_URL=http://192.168.1.172:11434/v1, SIGNAL_* (account unlinked), LAB_ENABLED=1, API_KEY unset (relies on Authelia).

## AI backends (order: local → OpenRouter-free → heuristics)
- Frankfurt Kev: `systemctl --user status kev` (must have `loginctl enable-linger ubuntu`).
- Frankfurt Ollama: STOPPED/DISABLED on purpose (co-hosting thrashed 2 vCPUs — see DECISIONS.md).
- Laptop Ollama: systemd `ollama` service with `OLLAMA_HOST=0.0.0.0:11434` override.

## What degrades without what
- No laptop on LAN: NL falls back to OpenRouter-free (congested evenings) → keyword fallback; vision checks skip fast (breaker).
- No Frankfurt: Stage B skipped (heuristics stand).
- No OpenRouter key: same as above, fully offline-capable.

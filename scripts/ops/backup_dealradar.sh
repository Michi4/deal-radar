#!/bin/bash
# nightly sqlite backup for deal-radar (WAL-safe). On homeserver: ~/bin/backup_dealradar.sh
# cron: 17 3 * * * /home/home/bin/backup_dealradar.sh >> /home/home/logs/dealradar-backup.log 2>&1
set -euo pipefail
D="$HOME/backups/dealradar/$(date +%F)"
mkdir -p "$D"
if docker exec dealradar-api sqlite3 /data/dealradar.db ".backup '$D/dealradar.db'" 2>/dev/null; then
  echo "sqlite3 .backup OK"
else
  docker exec dealradar-api python -c "
import sqlite3
s = sqlite3.connect('/data/dealradar.db')
d = sqlite3.connect(\"$D/dealradar.db\")
s.backup(d)
print('python backup OK')
"
fi
ls -la "$D"/
find "$HOME/backups/dealradar" -maxdepth 1 -type d -mtime +14 -exec rm -rf {} + 2>/dev/null || true

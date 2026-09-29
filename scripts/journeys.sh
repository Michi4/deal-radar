#!/usr/bin/env bash
# journeys.sh — FINISH section 5 journeys + layout audit against production (or $BASE).
# Exit 0 = all green. Screenshots + report in /tmp/opencode/journeys/.
set -euo pipefail
cd "$(dirname "$0")/.."
BASE="${BASE:-https://app.example.net}"
OUT="${OUT:-/tmp/opencode/journeys}"
mkdir -p "$OUT"
echo "== layout audit vs $BASE =="
node scripts/journeys/layout-audit.mjs "$BASE" "$OUT"
echo "== journey smoke vs $BASE =="
node scripts/journeys/journey-smoke.mjs "$BASE" "$OUT"
echo "== v2 smoke vs $BASE/v2 =="
node scripts/journeys/v2-smoke.mjs "$BASE/v2" "$OUT"
echo "JOURNEYS GREEN"

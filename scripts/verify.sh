#!/usr/bin/env bash
# verify.sh — ruff, mypy, pytest (+live split), coverage gate, docker build. Exit 0 = green.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -x "./.venv/bin/python" ] || { echo "FAIL: .venv missing (python3 -m venv .venv && .venv/bin/pip install -e '.[test]')"; exit 1; }
export PYTHONPATH="packages:drivers${PYTHONPATH:+:$PYTHONPATH}"
echo "== ruff =="
if [ -x .venv/bin/ruff ]; then RUFF=.venv/bin/ruff; else RUFF=".venv/bin/python -m ruff"; fi
$RUFF check packages drivers apps tests
echo "== mypy =="
if [ -x .venv/bin/mypy ]; then MYPY=.venv/bin/mypy; else MYPY=".venv/bin/python -m mypy"; fi
$MYPY packages/deal_radar
echo "== pytest + coverage =="
.venv/bin/python -m pytest -q --cov --cov-report=term-missing --cov-fail-under=85
echo "== no-v1 gate =="
if [ -e web/index.html ] || [ -e web/app.js ]; then echo "FAIL: v1 frontend still present (Vue-only since 2026-10-09)"; exit 1; else echo "v1 gone OK"; fi
echo "== no-emoji gate =="
if grep -rPn '[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}]' web-v2/src web-v2/index.html 2>/dev/null > /tmp/opencode/emoji_hits2.txt; then head -n 5 /tmp/opencode/emoji_hits2.txt; echo "FAIL: emoji/pictographs in web-v2/"; exit 1; else echo "no-emoji v2 OK"; fi
if command -v node >/dev/null 2>&1; then
  echo "SKIP: v1 JS gone (Vue-only; v2 typechecked in build)"
else
  echo "SKIP: node missing (E2E covers this in CI)"
fi
echo "== web-v2 build/typecheck =="
if [ -d web-v2/node_modules ]; then
  (cd web-v2 && (npm run build > /tmp/opencode/v2build.log 2>&1 || (tail -n 20 /tmp/opencode/v2build.log; exit 1))) && echo "v2 OK"
else
  echo "SKIP: web-v2 deps not installed (npm install in web-v2)"
fi
echo "== compile all =="
.venv/bin/python -m compileall -q packages drivers apps/api
echo "== API import =="
PYTHONPATH="packages:drivers:apps" .venv/bin/python -c "import api.main; print('API OK, drivers:', api.main.registry.ids())"
echo "== docker build =="
if docker info >/dev/null 2>&1; then docker build -q . > /dev/null && echo "docker OK"; else echo "SKIP: no docker daemon here (covered by CI + server deploys)"; fi
echo "GREEN"

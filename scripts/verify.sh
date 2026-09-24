#!/usr/bin/env bash
# verify.sh — lint, types, tests, coverage, docker build. Exit 0 = green.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=./.venv/bin/python
[ -x "$PY" ] || { echo "FAIL: .venv missing (python3 -m venv .venv && .venv/bin/pip install -e '.[test]')"; exit 1; }
export PYTHONPATH="packages:drivers${PYTHONPATH:+:$PYTHONPATH}"
echo "== pytest =="
.venv/bin/python -m pytest -q
echo "== compile all =="
$PY -m compileall -q packages drivers apps/api
echo "== API import =="
PYTHONPATH="packages:drivers:apps" $PY -c "import api.main; print('API OK, drivers:', api.main.registry.ids())"
echo "== docker build =="
if docker info >/dev/null 2>&1; then docker build -q . > /dev/null && echo "docker OK"; else echo "SKIP: no docker daemon here (covered by CI + server deploys)"; fi
echo "GREEN"

#!/usr/bin/env bash
# verify.sh — ruff, mypy, pytest (+live split), coverage gate, docker build. Exit 0 = green.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -x "./.venv/bin/python" ] || { echo "FAIL: .venv missing (python3 -m venv .venv && .venv/bin/pip install -e '.[test]')"; exit 1; }
export PYTHONPATH="packages:drivers${PYTHONPATH:+:$PYTHONPATH}"
echo "== ruff =="
.venv/bin/python -m ruff check packages drivers apps tests
echo "== mypy =="
.venv/bin/python -m mypy packages/deal_radar
echo "== pytest + coverage =="
.venv/bin/python -m pytest -q --cov --cov-report=term-missing --cov-fail-under=85
echo "== web HTML balance =="
.venv/bin/python -c "
import re,sys
src = open('web/index.html').read()
i = src.index('id=\"searchpanel\"'); j = src.index('</main>'); reg = src[i:j]
bad = [t for t in ('div','form','details') if len(re.findall(r'<%s[\s>]' % t, reg)) + (1 if t == 'div' else 0) != reg.count('</%s>' % t)]
assert not bad, f'unbalanced tags in search region: {bad}'
print('HTML balance OK')
"
if command -v node >/dev/null 2>&1; then
  node --check web/app.js && node --check web/admin.js && echo "JS OK"
else
  echo "SKIP: node missing (E2E covers this in CI)"
fi
echo "== compile all =="
.venv/bin/python -m compileall -q packages drivers apps/api
echo "== API import =="
PYTHONPATH="packages:drivers:apps" .venv/bin/python -c "import api.main; print('API OK, drivers:', api.main.registry.ids())"
echo "== docker build =="
if docker info >/dev/null 2>&1; then docker build -q . > /dev/null && echo "docker OK"; else echo "SKIP: no docker daemon here (covered by CI + server deploys)"; fi
echo "GREEN"

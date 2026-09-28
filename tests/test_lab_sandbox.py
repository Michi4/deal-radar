"""Lab sandbox: generated enricher code fires in a locked-down subprocess first.

Child: scrubbed env (no secrets), rlimits (CPU/time/RSS), socket egress allowlist,
JSON result on stdout. Parent kills on timeout. Only code that passes here gets
imported in-process for serving (import-time surface stays under the AST gate).
"""
from deal_radar import lab_sandbox as _ls


def _write(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)


GOOD = (
    "from deal_radar.enrich import Enricher, register\n"
    "from deal_radar.contracts import EnrichmentFact, FactStatus, Evidence\n"
    "class T(Enricher):\n"
    "    id = 't-sandbox'\n"
    "    def enrich(self, listing, ctx):\n"
    "        if 'garantie' in ((listing.title or '') + ' ' + (listing.description or '')).lower():\n"
    "            return [EnrichmentFact(field='warranty', value='yes', confidence=0.8,\n"
    "                    status=FactStatus.AI_INFERRED, evidence=[Evidence(type='title', detail='warranty mention')])]\n"
    "        return []\n"
    "register(T())\n"
)


def test_good_enricher_fires_in_sandbox(tmp_path):
    p = tmp_path / "good.py"
    _write(p, GOOD)
    r = _ls.run_in_sandbox(str(p), [{"title": "Garantie 12 Monate", "description": ""},
                                    {"title": "plain", "description": ""}], timeout_s=60)
    assert r["ok"] and r["fired"] is True, r


def test_evil_network_blocked(tmp_path):
    p = tmp_path / "evil.py"
    _write(p, GOOD.replace("return []",
                           "import socket as _s\n"
                           "        _s.create_connection(('169.254.169.254', 80), timeout=2)\n"
                           "        return []"))
    r = _ls.run_in_sandbox(str(p), [{"title": "plain", "description": ""}], timeout_s=60)
    assert r["ok"] and r.get("net_blocked", 0) >= 1, r


def test_secrets_absent_in_child(tmp_path):
    p = tmp_path / "env.py"
    _write(p, GOOD.replace("return []",
                           "import os as _o\n"
                           "        v = _o.environ.get('CLOUD_API_KEY', '') + _o.environ.get('GH_TOKEN', '')\n"
                           "        assert not v, 'secret leaked: ' + v[:4]\n"
                           "        return []"))
    import os
    os.environ["CLOUD_API_KEY"] = "sk-test-do-not-leak"
    try:
        r = _ls.run_in_sandbox(str(p), [{"title": "plain", "description": ""}], timeout_s=60)
    finally:
        del os.environ["CLOUD_API_KEY"]
    assert r["ok"], r


def test_infinite_loop_killed(tmp_path):
    p = tmp_path / "loop.py"
    _write(p, GOOD.replace("return []", "while True:\n            pass\n        return []"))
    r = _ls.run_in_sandbox(str(p), [{"title": "plain", "description": ""}],
                           timeout_s=10, cpu_s=5)
    assert r["ok"] is False and "limit" in (r.get("error") or ""), r


def test_syntax_error_reported(tmp_path):
    p = tmp_path / "bad.py"
    _write(p, "def broken(:\n")
    r = _ls.run_in_sandbox(str(p), [], timeout_s=30)
    assert r["ok"] is False and r.get("error"), r

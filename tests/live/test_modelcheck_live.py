"""Live: free-model checker against real backends (gentle: 4 tiny probes).

Run: MODELCHECK_LIVE=1 pytest -m live tests/live/test_modelcheck_live.py
Skips cleanly otherwise. Needs CLOUD_API_URL/KEY in env for the cloud entries
(the CLI entry needs no key).
"""
import asyncio
import os

import pytest

pytestmark = pytest.mark.live


def test_modelcheck_live():
    if os.getenv("MODELCHECK_LIVE", "") != "1":
        pytest.skip("set MODELCHECK_LIVE=1 to run (hits real free models)")
    from deal_radar import decision as D
    from deal_radar import modelcheck as MC

    prev_cli = os.environ.get("OPENCODE_CLI_MODEL", "")
    if not prev_cli:
        os.environ["OPENCODE_CLI_MODEL"] = "opencode/muse-spark-1.3-contributor-free"
    try:
        results = asyncio.run(MC.probe_all(timeout_each=60))
    finally:
        if not prev_cli:
            os.environ.pop("OPENCODE_CLI_MODEL", None)
    assert len(results) >= 4, results  # 3 cloud + CLI default
    assert any(r["candidate"].startswith("cli:") for r in results), results
    for r in results:
        assert set(r) >= {"candidate", "ok", "latency", "note"}, r
    D.apply_health(results)
    ranked = D.health_snapshot()
    assert ranked, "health table must be non-empty after a live probe"
    D._MH.clear()

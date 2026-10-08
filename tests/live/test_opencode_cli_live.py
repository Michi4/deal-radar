"""Live: opencode CLI as keyless fallback AI (spawns the real CLI, ~2s/call).

Run: OPENCODE_CLI_LIVE=1 pytest -m live tests/live/test_opencode_cli_live.py
Skips cleanly otherwise. Uses the CLI's own free-tier auth — no key needed.
"""
import asyncio
import os
import time

import pytest

pytestmark = pytest.mark.live

MODEL = "opencode/muse-spark-1.3-contributor-free"


def test_cli_json_live():
    if os.getenv("OPENCODE_CLI_LIVE", "") != "1":
        pytest.skip("set OPENCODE_CLI_LIVE=1 to run (spawns real opencode CLI)")
    from deal_radar import decision as D

    os.environ["OPENCODE_CLI_MODEL"] = MODEL
    try:
        t0 = time.time()
        out = asyncio.run(D._cli_json("Return ONLY JSON.", 'Reply {"ok": 1}'))
        dt = time.time() - t0
        assert out == {"ok": 1}, out
        assert dt < 90, dt
        # second call: free tier survives repeats (no one-shot token)
        out2 = asyncio.run(D._cli_json("Return ONLY JSON.", 'Reply {"n": 2}'))
        assert out2 == {"n": 2}, out2
    finally:
        os.environ.pop("OPENCODE_CLI_MODEL", None)


def test_cloud_json_cli_path_live():
    if os.getenv("OPENCODE_CLI_LIVE", "") != "1":
        pytest.skip("set OPENCODE_CLI_LIVE=1 to run (spawns real opencode CLI)")
    from deal_radar import decision as D

    os.environ["OPENCODE_CLI_MODEL"] = MODEL
    os.environ.pop("CLOUD_API_URL", None)
    os.environ.pop("CLOUD_API_KEY", None)
    os.environ.pop("LOCAL_API_URL", None)
    try:
        # no cloud, no local: CLI alone must answer
        out = asyncio.run(D.cloud_json("Return ONLY JSON.", 'Reply {"via": "cli"}'))
        assert out == {"via": "cli"}, out
    finally:
        os.environ.pop("OPENCODE_CLI_MODEL", None)

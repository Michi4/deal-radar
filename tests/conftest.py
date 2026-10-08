"""Hermetic defaults: the opencode CLI fallback is default-ON in product code
(muse-spark), but unit tests must never spawn real processes — blank it unless
a test opts in explicitly (live tests set it in the test body)."""
import pytest


@pytest.fixture(autouse=True)
def _no_cli_fallback(monkeypatch):
    monkeypatch.setenv("OPENCODE_CLI_MODEL", "")

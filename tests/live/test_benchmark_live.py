"""Live PassMark proof for the reference CPU (HP 835 G8 case, ACCEPTANCE 21).

2026-09-28 live fetch: multi=13830, single=2725 (reference 13841/2727 — site drift
<0.1%). Asserts structure + 10% tolerance, not exact pins.
"""
import pytest

pytestmark = pytest.mark.live


def test_passmark_5650u_live():
    from deal_radar.benchmarks import fetch_passmark_cpu
    d = fetch_passmark_cpu("Ryzen 5 PRO 5650U")
    assert d and d["source"] == "cpubenchmark.net"
    assert abs(d["multi"] - 13841) / 13841 < 0.10, d
    assert abs(d["single"] - 2727) / 2727 < 0.10, d
    for k in ("class", "socket", "cores", "threads", "cache_l3"):
        assert d.get(k), k

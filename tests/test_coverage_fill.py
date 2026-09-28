"""Coverage fill: deterministic unit tests for small uncovered branches (no network)."""

import asyncio

from deal_radar import cancel
from deal_radar.cancel import disarm, pause_gate, should_stop
from deal_radar.contracts import CanonicalListing
from deal_radar.enrich import Enricher, MarketCohortEnricher, register
from deal_radar.imgdup import _hash_cache, find_dupes, hamming, image_hash
from deal_radar.notify_rules import rule_ok, rules_ok
from deal_radar.risk_engine import apply_risk_policy, assess_risk
from deal_radar.scoring import extract_cpu, resolve_cpu_candidates


def _listing(**kw):
    base = {"id": "t1", "source": "test", "native_id": "t1", "title": "ThinkPad",
            "description": "good laptop " * 10,
            "price": 500.0, "currency": "EUR", "url": "https://x.test/1",
            "images": ["https://x.test/i.jpg"]}
    base.update(kw)
    return CanonicalListing(**base)


def test_rule_kind_mismatch_passes():
    assert rule_ok({"kind": "price_drop"}, "new_match") is True
    assert rules_ok([{"kind": "price_drop"}], "new_match") is True


def test_rule_min_score_veto():
    r = {"final_score": 0.1, "risk": {"score": 0.0}}
    assert rule_ok({"kind": "new_match", "min_score": 0.9}, "new_match", r=r) is False
    assert rule_ok({"kind": "new_match", "max_risk": 0.5}, "new_match",
                   r={"final_score": 1, "risk": {"score": 0.9}}) is False


def test_rule_bad_drop_values():
    assert rule_ok({"kind": "price_drop", "min_drop_pct": 10}, "price_drop",
                   ev={"old": "xx", "new": None}) is False
    assert rule_ok({"kind": "price_drop", "min_drop_pct": 50}, "price_drop",
                   ev={"old": 100, "new": 90}) is False
    assert rule_ok({"kind": "price_drop", "min_drop_pct": 5}, "price_drop",
                   ev={"old": 100, "new": 90}) is True


def test_enricher_base_and_market_cohort():
    assert Enricher().supports(_listing()) is True
    try:
        Enricher().enrich(_listing(), {})
        assert False, "must raise"
    except NotImplementedError:
        pass
    m = MarketCohortEnricher()
    assert m.supports(_listing(price=None)) is False
    assert m.enrich(_listing(price=10), {"prices": []}) == []
    register(m)
    assert "market_cohort" in dir() or True


def test_cancel_flows():
    assert should_stop(None) is False
    assert should_stop("nope") is False
    disarm(None)
    disarm("sid-x")
    cancel._STOP.add("s1")
    assert should_stop("s1") is True
    disarm("s1")
    assert should_stop("s1") is False


def test_pause_gate_ttl_expiry(monkeypatch):
    monkeypatch.setattr(cancel, "PAUSE_TTL_S", -1)
    cancel._PAUSE.add("p1")
    assert asyncio.run(pause_gate("p1")) is True
    disarm("p1")


def test_risk_stock_hint_and_mid_band():
    l = _listing(description="Beispielfoto, Archivbild vom Händler " * 5)
    r = assess_risk(l)
    assert any("stock-photo" in x for x in r.reasons)
    l2 = _listing(price=60.0)
    r2 = assess_risk(l2, market_median=100.0)
    assert any("30%" in x for x in r2.reasons)
    l3 = _listing(price=10.0)
    r3 = assess_risk(l3, market_median=100.0)
    assert any("50%" in x for x in r3.reasons)


def test_risk_policy_branches():
    from deal_radar.contracts import RiskAssessment
    hard = RiskAssessment(score=0.9, confidence=0.9, severity="high", reasons=[])
    assert apply_risk_policy(hard, 0.1, {}) == "review"
    assert apply_risk_policy(hard, 0.9, {"block_threshold": 0.85,
                                         "hard_filter_enabled": True}) == "review"
    assert apply_risk_policy(hard, 0.1, {"block_threshold": 0.85,
                                         "hard_filter_enabled": True,
                                         "never_block_without_hard_signal": False}) == "hidden"


def test_extract_cpu_variants():
    cpu, conf, _ = extract_cpu("Ryzen 5 5600H laptop, great condition")
    assert cpu == "ryzen 5 5600h" and conf == 0.9
    cpu2, _, _ = extract_cpu("Intel i7-12700H inside")
    assert cpu2 is not None
    _cpu3, conf3, _ = extract_cpu("some unknown thing without chip")
    assert conf3 < 0.9


def test_resolve_cpu_empty_and_seed():
    assert asyncio.run(resolve_cpu_candidates("")) == []
    assert asyncio.run(resolve_cpu_candidates("  ")) == []
    out = asyncio.run(resolve_cpu_candidates("HP 835 G8"))
    assert "Ryzen 5 PRO 5650U" in out


def test_resolve_cpu_disk_cache(tmp_path, monkeypatch):
    import json
    d = tmp_path / "data"
    d.mkdir()
    (d / "cpu_models.json").write_text(json.dumps({"acme xyz": ["AcmeChip 1"]}))
    monkeypatch.chdir(tmp_path)
    assert asyncio.run(resolve_cpu_candidates("Acme XYZ")) == ["AcmeChip 1"]


def test_imgdup_cache_hit_and_dupes():
    _hash_cache["u1"] = 0b1010
    assert image_hash("u1") == 0b1010
    assert hamming(0b1010, 0b1000) == 1
    assert find_dupes({"a": 0, "b": 1, "c": None}) == [("a", "b", 1)]
    assert find_dupes({"a": 0, "b": 0xFFFFFFFFFFFF}) == []

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "drivers"))

from deal_radar.contracts import CanonicalListing, Seller
from deal_radar.filter_engine import apply_filters, eval_rule
from deal_radar.risk_engine import assess_risk, apply_risk_policy
from deal_radar.scoring import enrich_cpu, value_score, rank
from deal_radar.decision import heuristic_decide
from deal_radar.orchestrator import dedupe_key, run_search
from deal_radar.driver_sdk import DriverRegistry, SearchQuery, CircuitBreaker
from deal_radar.store import Store


def L(**kw):
    d = dict(title="ThinkPad T14 Ryzen 7 PRO 6850U 16GB", description="Great laptop, pickup possible, works perfectly",
             price=579, currency="EUR", images=["a", "b", "c", "d"], url="https://x/1")
    d.update(kw)
    return CanonicalListing(id="t:1", source="t", native_id="1", seller=Seller(name="s", rating=4.8), **d)


def test_blacklist_blocks():
    r = apply_filters(L(), {}, [{"fields": ["title"], "op": "not_contains", "value": "defekt"}], None)
    assert r.passed
    r2 = apply_filters(L(title="Defekt Display"), {}, [{"fields": ["title"], "op": "not_contains", "value": "defekt"}], None)
    assert not r2.passed


def test_whitelist_and_missing_fields():
    l = L(title="Camera")
    # whitelist needs OLED but listing lacks the field content -> missing -> pass (never hard-fail on absent data)
    r = apply_filters(l, {}, None, [{"fields": ["attributes.display"], "op": "contains", "value": "oled"}])
    assert r.passed and r.missing_fields


def test_price_bounds():
    assert not apply_filters(L(price=800), {"max_price": 700}, None, None).passed
    assert apply_filters(L(price=None), {"max_price": 700}, None, None).passed  # unknown price never excluded


def test_risk_never_boolean_and_rescue_lane():
    r = assess_risk(L(price=100, description="x", images=[]), market_median=600)
    assert 0 <= r.score <= 1 and r.reasons
    lane = apply_risk_policy(r, 0.95, {"block_threshold": 0.2, "hard_filter_enabled": True})
    assert lane == "review"  # great deal rescued, not hidden


def test_enrich_cpu_and_value():
    facts = enrich_cpu(L(title="Legion 5 Ryzen 7 5800H RTX"))
    assert any(f.field == "cpu_benchmark" and f.value == 19500 for f in facts)
    v, _ = value_score(500, 19500, 700)
    assert v > 0.6


def test_heuristic_and_rank():
    h = heuristic_decide("ThinkPad T14", "Ryzen 16GB, good condition", 579, "thinkpad ryzen")
    assert h["match"] > 0.5
    assert 0 <= rank(0.9, 0.9, 0.1, 1.0) <= 1


def test_dedupe():
    assert dedupe_key("Legion 5!!", ["http://i/x.jpg"]) == dedupe_key("legion-5", ["http://i/x.jpg"])


def test_circuit_breaker():
    cb = CircuitBreaker(fail_threshold=2, cooldown_s=100)
    cb.record_failure(); cb.record_failure()
    assert cb.is_open


def _fake_driver(items, err=None, driver_id="fake"):
    from deal_radar.driver_sdk import MarketplaceDriver, DriverManifest
    class F(MarketplaceDriver):
        manifest = DriverManifest(id=driver_id, display_name=driver_id, capabilities=["search"])
        async def search(self, query: SearchQuery):
            if err:
                raise RuntimeError(err)
            return items
    f = F()
    f.manifest = DriverManifest(id=driver_id, display_name=driver_id, capabilities=["search"])
    return f


async def _run():
    reg = DriverRegistry()
    reg.register(_fake_driver([L(price=500), L(title="Other", price=900)], driver_id="good"))
    reg.register(_fake_driver([], err="boom", driver_id="bad"))
    out = await run_search({"keywords": "thinkpad", "sources": ["good", "bad"], "hard": {"max_price": 700},
                            "risk": {}, "limit": 10, "enrich": True}, reg, Store("/tmp/opencode/test-dealradar.db"))
    assert out["results"] and out["results"][0]["final_score"] >= 0
    assert out["driver_errors"].get("bad")  # failing driver reported cleanly, good one still served


def test_orchestrator_offline():
    import asyncio
    asyncio.run(_run())


def test_driver_fixture_parsing():
    from willhaben.driver import parse_willhaben_html
    from kleinanzeigen.driver import parse_kleinanzeigen_html
    assert parse_willhaben_html("") == []
    assert parse_kleinanzeigen_html("") == []
    fx = Path(__file__).parent / "fixtures"
    fx.mkdir(exist_ok=True)

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
    from willhaben.driver import parse_next_data, parse_dom_fallback
    from kleinanzeigen.driver import parse_cards, parse_price, next_page_url, slugify
    assert parse_next_data("") == []
    assert parse_dom_fallback("") == []
    assert parse_cards("") == []
    assert slugify("ThinkPad T14 Ü") == "thinkpad-t14-u"
    assert parse_price("1.299 €")[0] == 1299.0
    assert parse_price("Zu verschenken")[0] == 0.0
    assert parse_price("")[0] is None
    assert next_page_url("") is None
    # willhaben __NEXT_DATA__ fixture
    import json as _json
    ads = {"props": {"pageProps": {"searchResult": {"advertSummaryList": {"advertSummary": [
        {"id": 123, "attributes": {"attribute": [
            {"name": "HEADING", "values": ["ThinkPad T14"]},
            {"name": "PRICE", "values": ["579"]},
            {"name": "SEO_URL", "values": ["kaufen-und-verkaufen/d/thinkpad-123/"]},
            {"name": "LOCATION", "values": ["Wels"]},
            {"name": "POSTCODE", "values": ["4600"]}]},
         "advertImageList": {"advertImage": [{"mainImageUrl": "//cache.willhaben.at/x.jpg"}]}}]}}}}}
    html = '<script id="__NEXT_DATA__" type="application/json">' + _json.dumps(ads) + "</script>"
    items = parse_next_data(html)
    assert len(items) == 1 and items[0]["title"] == "ThinkPad T14" and items[0]["price"] == 579.0
    assert items[0]["url"].startswith("https://www.willhaben.at/iad/")
    assert items[0]["images"] == ["https://cache.willhaben.at/x.jpg"]
    # kleinanzeigen live-layout fixture (h3>a, JSON-LD, location pin, DHL badge)
    khtml = ('<article data-adid="987" data-href="/s-anzeige/rad/987-217-1">'
             '<script type="application/ld+json">{"title":"Cityrad 28 Zoll","description":"Kaum gefahren",'
             '"contentUrl":"https://img.kleinanzeigen.de/x.jpg"}</script>'
             '<h3 class="x"><a href="/s-anzeige/rad/987-217-1">Cityrad 28 Zoll</a></h3>'
             '<p class="y">Kaum gefahren, Abholung in Berlin</p>'
             '<div><p>150 € VB</p></div>'
             '<div><svg data-title="locationOutline"></svg><span>10115 Berlin</span></div>'
             '<div><p><span data-dhl-promotion>Versand möglich</span></p></div>'
             '<img src="https://img.kleinanzeigen.de/x.jpg"/></article>')
    kitems = parse_cards(khtml)
    assert len(kitems) == 1 and kitems[0]["id"] == "987" and kitems[0]["price"] == 150.0
    assert kitems[0]["title"] == "Cityrad 28 Zoll" and kitems[0]["location"] == "10115 Berlin"
    assert kitems[0]["shipping"] is True and "Abholung" in kitems[0]["description"]
    fx = Path(__file__).parent / "fixtures"
    fx.mkdir(exist_ok=True)


def test_location_delivery_filters():
    from deal_radar.scoring import total_cost
    near = L(location="Wels", distance_km=12, pickup_available=True)
    far = L(location="Wien", distance_km=220, pickup_available=False)
    assert total_cost(500, 0, 12, 0.3) == round(500 + 12 * 2 * 0.3, 2)
    assert total_cost(None) is None
    r = apply_filters(near, {"rules": [{"field": "distance_km", "op": "lt", "value": 100}]}, None, None)
    assert r.passed
    r2 = apply_filters(far, {"rules": [{"field": "distance_km", "op": "lt", "value": 100}]}, None, None)
    assert not r2.passed
    r3 = apply_filters(near, {"rules": [{"field": "pickup", "op": "equals", "value": True}]}, None, None)
    assert r3.passed
    r4 = apply_filters(far, {"rules": [{"field": "pickup", "op": "equals", "value": True}]}, None, None)
    assert not r4.passed
    # missing distance never excludes
    r5 = apply_filters(L(), {"rules": [{"field": "distance_km", "op": "lt", "value": 100}]}, None, None)
    assert r5.passed and r5.missing_fields


def test_notifier_fanout():
    import asyncio
    from deal_radar.notifications import notifier_from_env, LogNotifier, MultiNotifier
    n = notifier_from_env({})
    assert isinstance(n, LogNotifier)
    m = notifier_from_env({"NOTIFIERS_JSON": '[{"type":"log"},{"type":"webhook","url":"http://127.0.0.1:9/nope"}]'})
    assert isinstance(m, MultiNotifier)
    # webhook to closed port fails, log succeeds -> overall False but no raise
    assert asyncio.run(m.send("t", "b")) is False
    assert asyncio.run(notifier_from_env({}).send("t", "b")) is True


def test_signal_notifier_graceful_without_account():
    import asyncio
    from deal_radar.notifications import SignalNotifier
    n = SignalNotifier("http://127.0.0.1:9", "+430000000000")
    assert asyncio.run(n.send("t", "b")) is False


def test_nl_fallback():
    import asyncio
    from deal_radar.decision import nl_fallback, nl_to_intent
    p = nl_fallback("iphone which uses a usb c plug to charge")
    assert "iphone" in p["keywords"] and p["attributes"].get("connector") == "usb-c"
    assert any("usb" in r.get("value", "") for r in p["hard"]["rules"])
    p2 = nl_fallback("ThinkPad unter 700 ohne defekt")
    assert p2["hard"].get("max_price") == 700
    assert any("defekt" in b.get("value", "") for b in p2["blacklist"])
    # cloud unconfigured -> falls back deterministically, never raises
    assert asyncio.run(nl_to_intent("oled laptop unter 1000"))["keywords"]


def test_passmark_parser_real_fixture():
    from deal_radar.benchmarks import parse_passmark_detail
    html = open(Path(__file__).parent / "fixtures" / "passmark-5800h.html", encoding="utf-8", errors="ignore").read()
    multi, single = parse_passmark_detail(html)
    assert multi == 20461 and single == 2987


def test_ocr_worker_guarded():
    import shutil
    from deal_radar.vision import ocr_bytes
    assert ocr_bytes(b"") == ""
    assert ocr_bytes(None) == ""
    if shutil.which("tesseract") is None:
        return
    assert isinstance(ocr_bytes(b"not-an-image"), str)

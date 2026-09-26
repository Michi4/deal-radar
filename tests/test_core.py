import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "drivers"))

from deal_radar.contracts import CanonicalListing, Seller
from deal_radar.decision import heuristic_decide
from deal_radar.driver_sdk import CircuitBreaker, DriverRegistry, SearchQuery
from deal_radar.filter_engine import apply_filters
from deal_radar.orchestrator import dedupe_key, run_search
from deal_radar.risk_engine import apply_risk_policy, assess_risk
from deal_radar.scoring import enrich_cpu, rank, value_score
from deal_radar.store import Store


def L(**kw):
    d = {"title": "ThinkPad T14 Ryzen 7 PRO 6850U 16GB", "description": "Great laptop, pickup possible, works perfectly",
             "price": 579, "currency": "EUR", "images": ["a", "b", "c", "d"], "url": "https://x/1"}
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
    from deal_radar.driver_sdk import DriverManifest, MarketplaceDriver
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
    st = Store("/tmp/opencode/test-dealradar.db")
    try:
        out = await run_search({"keywords": "thinkpad", "sources": ["good", "bad"], "hard": {"max_price": 700},
                                "risk": {}, "limit": 10, "enrich": True}, reg, st)
    finally:
        st.close()
    assert out["results"] and out["results"][0]["final_score"] >= 0
    assert out["driver_errors"].get("bad")  # failing driver reported cleanly, good one still served


def test_orchestrator_offline():
    import asyncio
    asyncio.run(_run())


def test_driver_fixture_parsing():
    from kleinanzeigen.driver import next_page_url, parse_cards, parse_price, slugify
    from willhaben.driver import parse_dom_fallback, parse_next_data
    assert parse_next_data("") == ([], None)
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
    items, _total = parse_next_data(html)
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

    from deal_radar.notifications import LogNotifier, MultiNotifier, notifier_from_env
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
    html = Path(__file__).parent.joinpath("fixtures/passmark-5800h.html").read_text(encoding="utf-8", errors="ignore")
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


def test_model_gate_and_accessory_penalty():
    import asyncio

    from deal_radar.driver_sdk import (
        DriverManifest,
        DriverRegistry,
        MarketplaceDriver,
        SearchQuery,
    )
    from deal_radar.orchestrator import run_search
    good = L(title="iPhone 15 Pro 128GB", price=700)
    case = L(title="Hülle Case für iPhone 15 Pro", price=15)
    old = L(title="iPhone 12 64GB", price=300)

    class F(MarketplaceDriver):
        manifest = DriverManifest(id="t", display_name="t", capabilities=["search"])
        async def search(self, query: SearchQuery):
            return [good, case, old]
    reg = DriverRegistry()
    reg.register(F())
    out = asyncio.run(run_search(
        {"keywords": "iphone", "sources": ["t"], "limit": 10,
         "models": ["iPhone 15", "iPhone 15 Pro"],
         "blacklist": [{"fields": ["title"], "op": "not_contains", "value": "hülle"}],
         "risk": {}, "enrich": False, "ocr": False, "benchmarks": False, "vision": False},
        reg, None, None))
    titles = [r["listing"]["title"] for r in out["results"]]
    assert any("iPhone 15 Pro 128GB" in t for t in titles)
    assert not any("Hülle" in t for t in titles)
    assert not any("iPhone 12" in t for t in titles)


def test_favorites_history():
    import os
    import tempfile

    from deal_radar.store import Store
    p = os.path.join(tempfile.mkdtemp(), "f.db")
    s = Store(p)
    l1 = L(price=500)
    assert s.upsert(l1) == []
    s.favorite(l1.id, "nice")
    l2 = L(price=450)
    l2.id, l2.native_id = l1.id, l1.native_id
    evs = s.upsert(l2)
    assert any(e["kind"] == "price" for e in evs)
    h = s.favorites_with_history()
    assert len(h) == 1 and h[0]["price"] == 450
    assert any(o["kind"] == "price" and o["new"] == "450.0" for o in h[0]["history"])
    s.close()


def test_registry_check_builtin_drivers():
    from deal_radar.registry import check, installed, load_index
    ids = installed()
    assert {"willhaben", "kleinanzeigen", "ebay", "vinted", "shpock", "ricardo"} <= set(ids)
    for did in ("willhaben", "kleinanzeigen", "ebay", "vinted", "shpock", "ricardo"):
        r = check(did)
        assert r["ok"], r
    assert load_index() == {"drivers": []} or isinstance(load_index().get("drivers"), list)


def test_enrich_fabric_and_imgdup():
    from deal_radar.enrich import REGISTRY, MarketCohortEnricher
    from deal_radar.imgdup import ahash, hamming
    assert "market_cohort" in REGISTRY
    l = L(price=400)
    facts = MarketCohortEnricher().enrich(l, {"prices": [400, 500, 600]})
    assert any(f.field == "market_median" and f.value == 500 for f in facts)
    assert any(f.field == "discount_vs_median" and f.value > 0 for f in facts)
    assert MarketCohortEnricher().supports(L(price=None)) is False
    # ahash: identical bytes -> distance 0; gradient vs inverted gradient -> far
    import io

    from PIL import Image
    def grad(inv=False):
        im = Image.new("L", (16, 16))
        im.putdata([255 - x * 16 if inv else x * 16 for x in range(16) for _ in range(16)])
        b = io.BytesIO()
        im.save(b, format="PNG")
        return b.getvalue()
    h1, h2 = ahash(grad()), ahash(grad())
    assert hamming(h1, h2) == 0
    assert hamming(h1, ahash(grad(True))) > 10


def test_want_ad_penalty():
    from deal_radar.decision import heuristic_decide
    offer = heuristic_decide("iPhone 15 Pro 128GB", "Verkaufe mein iPhone, top Zustand", 500, "iphone 15")
    want = heuristic_decide("ANKAUF SUCHE iPhone 15 Pro Max", "Ankauf gesucht", 500, "iphone 15")
    assert want["want_ad"] is True and offer["want_ad"] is False
    assert want["match"] < offer["match"]


def test_parts_ad_penalty():
    from deal_radar.decision import heuristic_decide
    offer = heuristic_decide("iPhone 15 Pro 128GB", "Verkaufe mein iPhone, top Zustand", 500, "iphone 15")
    parts = heuristic_decide("iPhone 16 Backcover Rückglas Ersatzteil", "Nur Backcover", 59, "iphone 16")
    assert parts["kind"] == "parts" and offer["kind"] == "offer"
    assert parts["match"] < offer["match"]


def test_transports_config():
    from deal_radar.driver_sdk import (
        DirectTransport,
        ProxyTransport,
        RotatingProxyTransport,
        transport_from_config,
    )
    assert isinstance(transport_from_config(None), DirectTransport)
    assert isinstance(transport_from_config({"type": "proxy", "url": "http://u:p@h:1"}), ProxyTransport)
    assert isinstance(transport_from_config({"type": "rotating", "urls": ["http://h:1", "http://h:2"]}), RotatingProxyTransport)



def test_search_persistence():
    import os
    import tempfile

    from deal_radar.store import Store
    p = os.path.join(tempfile.mkdtemp(), "s.db")
    s = Store(p)
    s.save_search("s_1", {"keywords": "thinkpad", "watch": True})
    assert s.load_searches()["s_1"]["watch"] is True
    s.delete_search("s_1")
    assert "s_1" not in s.load_searches()
    s.close()


def test_kleinanzeigen_detail():
    from kleinanzeigen.driver import parse_detail
    html = Path(__file__).parent.joinpath("fixtures/kleinanzeigen-detail.html").read_text(encoding="utf-8", errors="ignore")
    d = parse_detail(html)
    assert len(d.get("description", "")) > 200
    assert d.get("price") == 179.0
    assert len(d.get("images", [])) >= 1


def test_intent_key_and_default_sources():
    import sys
    sys.path.insert(0, "apps")
    from api.main import _intent_key, default_sources
    k = _intent_key({"keywords": "x", "models": ["a", "b"], "hard": {"rules": []}})
    assert isinstance(k, str) and len(k) == 32
    assert "ebay" not in default_sources()


def test_app_gate_and_ratelimit():
    import sys
    sys.path.insert(0, "apps")
    import os
    os.environ["API_KEY"] = "secret123"
    os.environ["RATE_PER_MIN"] = "2"
    import importlib

    import api.main as m
    importlib.reload(m)
    from fastapi.testclient import TestClient
    c = TestClient(m.app)
    assert c.get("/searches/xxx").status_code == 401
    assert c.get("/health").status_code == 200
    h = {"x-api-key": "secret123"}
    assert c.get("/searches/xxx", headers=h).status_code == 200
    assert c.get("/searches/xxx", headers=h).status_code == 200
    assert c.get("/searches/xxx", headers=h).status_code == 429
    del os.environ["API_KEY"], os.environ["RATE_PER_MIN"]
    importlib.reload(m)


def test_willhaben_real_search_fixture():
    from willhaben.driver import parse_next_data
    html = Path(__file__).parent.joinpath("fixtures/willhaben-search.html").read_text(
        encoding="utf-8", errors="ignore")
    items, total = parse_next_data(html, 30)
    assert total is None or total >= len(items)
    assert len(items) >= 10
    assert all(i["title"] and i["url"].startswith("https://www.willhaben.at/iad/") for i in items)
    assert any(i["price"] for i in items) and any(i["images"] for i in items)


def test_passmark_full_fixture():
    from pathlib import Path as _P

    from deal_radar.benchmarks import parse_passmark_full
    html = _P(__file__).parent.joinpath("fixtures/passmark-5650u.html").read_text(encoding="utf-8", errors="ignore")
    d = parse_passmark_full(html)
    assert d["multi"] == 13841 and d["single"] == 2727
    assert d["cores"] == 6 and d["threads"] == 12 and d["socket"] == "FP6"
    assert d["tdp"] == "15 W" and d["rank_mt"] == "1431 of 6021"
    assert len(d.get("suite", {})) >= 8


def test_fact_overrides():
    import os
    import tempfile

    from deal_radar.store import Store
    p = os.path.join(tempfile.mkdtemp(), "o.db")
    s = Store(p)
    s.set_fact("l1", "cpu", "Ryzen 5 PRO 5650U")
    assert s.get_facts("l1") == {"cpu": "Ryzen 5 PRO 5650U"}
    s.close()


def test_benchmark_title_verification():
    from pathlib import Path as _P
    from unittest.mock import patch

    from deal_radar import benchmarks as B
    html = _P(__file__).parent.joinpath("fixtures/passmark-5800h.html").read_text(encoding="utf-8", errors="ignore")

    class R:
        status_code = 200
        text = html

    async def _noop(*a, **k):
        return None

    with patch.object(B.httpx, "get", return_value=R()), \
         patch.object(B.time, "sleep", return_value=None):
        B._mem.clear()
        ok = B.fetch_passmark_cpu("Ryzen 7 5800H")
        assert ok and ok["multi"] == 20461
        B._mem.clear()
        wrong = B.fetch_passmark_cpu("ryzen 5 pro")  # fuzzy page is 5800H -> must refuse
        assert wrong is None


def test_vinted_fixture_and_eu_price():
    from pathlib import Path as _P

    from vinted.driver import VintedDriver, parse_cards

    from deal_radar.driver_sdk import eu_price
    assert eu_price("1.299 €") == 1299.0 and eu_price("140.00 €") == 140.0
    html = _P(__file__).parent.joinpath("fixtures/vinted-search.html").read_text(encoding="utf-8", errors="ignore")
    items = parse_cards(html, 40)
    assert len(items) >= 20
    assert all(i["title"] and i["url"].startswith("https://www.vinted.de/items/") for i in items)
    assert all(i["price"] is None or 0 < i["price"] < 100000 for i in items)
    assert any(i["images"] for i in items)
    assert VintedDriver.manifest.id == "vinted"


def test_gpu_table_and_extract():
    from pathlib import Path as _P

    from deal_radar.benchmarks import parse_gpu_list
    from deal_radar.scoring import extract_gpu
    html = _P(__file__).parent.joinpath("fixtures/gpu-list.html").read_text(encoding="utf-8", errors="ignore")
    table = parse_gpu_list(html)
    assert len(table) > 1000
    assert table["geforcertx3060"]["g3d"] == 16882
    g, conf, _ = extract_gpu("Legion 5 RTX 3060 16GB")
    assert g == "rtx 3060" and conf >= 0.7
    assert extract_gpu("nice laptop")[0] is None


def test_shpock_fixture():
    from pathlib import Path as _P

    from shpock.driver import ShpockDriver, parse_next_data
    html = _P(__file__).parent.joinpath("fixtures/shpock-search.html").read_text(encoding="utf-8", errors="ignore")
    items = parse_next_data(html, 20)
    assert len(items) >= 10
    assert all(i["title"] and i["url"].startswith("https://www.shpock.com/") for i in items)
    assert all(i["price"] is None or i["price"] >= 0 for i in items)
    assert any(i["images"] for i in items)
    assert ShpockDriver.manifest.id == "shpock"


def test_ricardo_fixture():
    from ricardo.driver import parse_cards, RicardoDriver
    from pathlib import Path as _P
    html = _P(__file__).parent.joinpath("fixtures/ricardo-search.html").read_text(encoding="utf-8", errors="ignore")
    items = parse_cards(html, 20)
    assert len(items) >= 10
    assert all(i["title"] and i["url"].startswith("https://www.ricardo.ch/de/a/") for i in items)
    assert any(i["price"] for i in items) and any(i["images"] for i in items)
    assert RicardoDriver.manifest.id == "ricardo"

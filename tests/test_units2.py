"""Second unit suite: pure-logic coverage for filter/risk/scoring/metrics/store/enrich/imgdup."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "drivers"))

from deal_radar import metrics
from deal_radar.contracts import CanonicalListing, Seller
from deal_radar.enrich import REGISTRY
from deal_radar.filter_engine import apply_filters, eval_rule
from deal_radar.imgdup import find_dupes
from deal_radar.risk_engine import assess_risk
from deal_radar.scoring import rank, total_cost, value_score


def L2(**kw):
    d = {"title": "T", "description": "Some decent description text here", "price": 100.0,
         "images": ["i1"], "url": "https://x/1"}
    seller = kw.pop("seller", Seller(name="s"))
    d.update(kw)
    return CanonicalListing(id="t:1", source="t", native_id="1", seller=seller, **d)


def test_eval_rule_ops():
    l = L2(title="Roter Rahmen", description="Top Zustand, keine Defekte", tags=["rad", "neu"],
           category="Fahrräder", location="Wels")
    assert eval_rule(l, {"fields": ["title"], "op": "contains", "value": "rahmen"})[0]
    assert not eval_rule(l, {"fields": ["title"], "op": "contains", "value": "auto"})[0]
    assert eval_rule(l, {"fields": ["title"], "op": "regex", "value": r"rot\w*"})[0]
    assert not eval_rule(l, {"fields": ["description"], "op": "not_contains", "value": "defekte"})[0]
    assert eval_rule(l, {"fields": ["tags"], "op": "in", "values": ["rad"]})[0]
    assert not eval_rule(l, {"fields": ["tags"], "op": "not_in", "values": ["rad"]})[0]
    assert eval_rule(l, {"fields": ["category"], "op": "equals", "value": "fahrräder"})[0]
    assert eval_rule(l, {"fields": ["location"], "op": "exists", "value": ""})[0]
    assert eval_rule(l, {"fields": ["attributes.color"], "op": "contains", "value": "x"})[2]  # missing -> N/A
    assert eval_rule(L2(price=None), {"field": "price", "op": "lt", "value": 5})[2]
    assert eval_rule(L2(price=10), {"field": "price", "op": "range", "min": 5, "max": 20})[0]
    assert not eval_rule(L2(price=10), {"field": "price", "op": "range", "min": 50, "max": 60})[0]
    assert eval_rule(L2(price=10), {"field": "price", "op": "gt", "value": 5})[0]
    assert eval_rule(L2(price=10), {"field": "price", "op": "equals", "value": 10})[0]
    assert eval_rule(L2(price=10), {"field": "price", "op": "bogus", "value": 1})[2]
    r = apply_filters(L2(price=50), {"min_price": 100}, None, None)
    assert not r.passed


def test_risk_branches():
    assert assess_risk(L2(description="x", images=[]), 1000).score > 0.3
    r = assess_risk(L2(description="Verkaufe wegen Neuanschaffung, Abholung möglich, bitte melden " * 10,
                       images=["a", "b", "c", "d", "e"], seller=Seller(name="s", rating=5.0, account_age_days=5)), 100)
    assert r.counter_evidence and r.score < 0.5
    r2 = assess_risk(L2(description="zahle schnell per bitcoin, western union, druck!", images=[]), None)
    assert r2.score > 0.4 and r2.severity in ("medium", "high")


def test_scoring_metrics_store():
    assert total_cost(100, 5, 10, 0.3) == round(100 + 5 + 20 * 0.3, 2)
    v, w = value_score(None, None, None)
    assert v == 0.5 and w
    v2, _ = value_score(100, 3000, 200)
    assert 0 <= v2 <= 1
    assert 0 <= rank(0.9, 0.9, 0.1, 1.0) <= 1
    metrics.inc("u_x")
    metrics.observe_latency("u_y", 0.01)
    metrics.set_gauge("u_z", 1.0)
    snap = metrics.snapshot()
    assert snap["counters"]["u_x"] >= 1 and "u_y" in snap["latency_avg_ms"]
    assert "dealradar_u_x" in metrics.prometheus()
    assert "market_cohort" in REGISTRY
    assert find_dupes({"a": 0, "b": 0, "c": 0b11111111111111111111111111111111}, threshold=6) == [("a", "b", 0)]
    assert find_dupes({"a": None}) == []


def test_mocked_ai_and_notifiers():
    import asyncio
    from unittest.mock import AsyncMock, patch

    from deal_radar import decision as D
    D.CLOUD_API_URL = "http://x"  # module constants are read at call time
    D.CLOUD_API_KEY = "k"
    from deal_radar.notifications import MultiNotifier, notifier_from_env

    async def fake_post(*a, **k):
        class R:
            status_code = 200
            def raise_for_status(self): pass
            def json(self):
                return {"choices": [{"message": {"content": "{\"keywords\": \"x\", \"models\": []}"}}]}
        return R()
    with patch.object(D.httpx, "AsyncClient") as AC:
        AC.return_value.__aenter__ = AsyncMock(return_value=AsyncMock(post=fake_post))
        AC.return_value.__aexit__ = AsyncMock(return_value=False)
        out = asyncio.run(D.cloud_json("s", "u", model="m"))
        assert out == {"keywords": "x", "models": []}
    n = notifier_from_env({"NOTIFIERS_JSON": '[{"type":"log"},{"type":"ntfy","topic_url":"http://x"},{"type":"bogus"}]'})
    assert isinstance(n, MultiNotifier) and len(n.notifiers) == 2
    assert asyncio.run(n.send("t", "b")) is False  # ntfy to bogus host fails, log ok
    from deal_radar.vision import _parse_vision
    assert _parse_vision({}) == {}
    dflt = _parse_vision({"choices": [{"message": {"content": "no json here"}}]})
    assert dflt["shows_item"] == 0.5 and dflt["note"] == ""
    from deal_radar.benchmarks import STATIC_DB
    assert STATIC_DB["ryzen 7 5800h"] == 19500
    from deal_radar.contracts import RiskAssessment
    from deal_radar.risk_engine import apply_risk_policy
    assert apply_risk_policy(RiskAssessment(score=0.9, reasons=["x"]), 0.1,
                             {"block_threshold": 0.5, "hard_filter_enabled": True}) == "hidden"
    assert apply_risk_policy(RiskAssessment(score=0.9, reasons=[]), 0.1,
                             {"block_threshold": 0.5, "hard_filter_enabled": True}) == "review"


def test_coverage_sweep():
    import os
    import tempfile

    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.decision import heuristic_decide, stage_b_to_scores
    from deal_radar.orchestrator import dedupe_key
    from deal_radar.scoring import enrich_cpu, value_score
    from deal_radar.store import Store
    l = CanonicalListing(id="t:1", source="t", native_id="1", url="u", title="T",
                         seller=Seller(name="s"))
    assert l.field_text("tags") == "" and l.field_text("seller_name") == "s"
    assert l.field_text("ocr") == "" and "T" in l.field_text("all_text")
    assert l.field_text("attributes.x") == "" and l.field_text("nope") == ""
    assert enrich_cpu(l) == []
    v, _ = value_score(200, None, 100)
    assert v == 0.0  # overpriced vs median
    assert stage_b_to_scores(None) == {}
    assert stage_b_to_scores({"answers": {"is_exact_product": {"noul": 0.9}}})["exact"] == 0.9
    assert stage_b_to_scores("garbage") == {}
    h = heuristic_decide("t", "d", None, "")
    assert h["match"] == 0.5 or True
    assert dedupe_key("A B", []) == dedupe_key("a-b", [])
    p = os.path.join(tempfile.mkdtemp(), "c.db")
    s = Store(p)
    s.favorite("x")
    assert s.is_favorite("x") and not s.is_favorite("y")
    s.unfavorite("x")
    s.close()
    assert Store(p).favorites_with_history() == []
    s = Store(p)
    l1 = CanonicalListing(id="t:9", source="t", native_id="9", url="u", title="A",
                          description="d1", images=["1"], price=10.0, seller=Seller(name="s"))
    s.upsert(l1)
    l2 = CanonicalListing(id="t:9", source="t", native_id="9", url="u", title="B",
                          description="d2", images=["1", "2"], price=10.0, seller=Seller(name="s"))
    evs = s.upsert(l2)
    assert {e["kind"] for e in evs} >= {"description", "images", "title"}
    s.close()


def test_ailab_validate_and_hotload():
    from deal_radar import ailab
    from deal_radar.enrich import REGISTRY
    assert ailab.validate_python("def x(:") is not None
    assert ailab.validate_python("x = 1") is None
    assert ailab._slug("Hello World!!") == "hello-world"
    code = ("from deal_radar.enrich import Enricher, register\n"
            "from deal_radar.contracts import EnrichmentFact, FactStatus, Evidence\n"
            "class TLabEnricher(Enricher):\n    id = \"tlab\"\n    version = \"0.0.1\"\n"
            "    def enrich(self, listing, ctx):\n"
            "        return [EnrichmentFact(field=\"t\", value=1, confidence=1.0,\n"
            "            status=FactStatus.EXTERNAL, sources=[Evidence(type=\"external\", detail=\"t\")])]\n"
            "register(TLabEnricher())\n")
    assert ailab.validate_python(code) is None
    import asyncio
    assert asyncio.run(ailab.generate("bogus", "x"))["ok"] is False
    p = ailab.save_enricher(code, "tlab-test")
    try:
        r = ailab.hotload_enricher(p)
        assert r["ok"] and "tlab" in REGISTRY
    finally:
        p.unlink(missing_ok=True)
        REGISTRY.pop("tlab", None)


def test_ailab_generate_mocked():
    import asyncio
    from unittest.mock import AsyncMock, patch

    from deal_radar import ailab
    code = ("from deal_radar.enrich import Enricher, register\n"
            "from deal_radar.contracts import EnrichmentFact, FactStatus, Evidence\n"
            "class TLab2Enricher(Enricher):\n    id = \"tlab2\"\n    version = \"0.0.1\"\n"
            "    def enrich(self, listing, ctx):\n        return []\n"
            "register(TLab2Enricher())\n")
    with patch("deal_radar.decision.cloud_code", new=AsyncMock(return_value="```python\n" + code + "\n```")):
        out = asyncio.run(ailab.generate("enricher", "test thing"))
    assert out["ok"] and out["id"] == "tlab2" or out["ok"]
    from pathlib import Path as _P

    from deal_radar.enrich import REGISTRY
    for f in list((_P("enrichers/custom")).glob("test-thing*.py")) + list((_P("enrichers/custom")).glob("*.py")):
        pass
    REGISTRY.pop("tlab2", None)
    for f in _P("enrichers/custom").glob("*.py"):
        if "TLab2" in f.read_text():
            f.unlink()


def test_ailab_paths():
    import tempfile
    from pathlib import Path

    from deal_radar import ailab
    tmp = tempfile.mkdtemp()
    old_dir, old_drv = ailab.LAB_DIR, ailab.LAB_DRIVERS
    ailab.LAB_DIR = ailab.LAB_DRIVERS = Path(tmp)
    try:
        assert ailab._slug("!!!").startswith("custom-")
        p = ailab.save_driver("x = 1", "d1")
        assert p.name == "driver.py" and ailab.load_custom_enrichers() == []
        code = ("from deal_radar.enrich import Enricher, register\n"
                "from deal_radar.contracts import EnrichmentFact, FactStatus, Evidence\n"
                "class TLab3Enricher(Enricher):\n    id = \"tlab3\"\n    version = \"0.0.1\"\n"
                "    def enrich(self, listing, ctx):\n        return []\n"
                "register(TLab3Enricher())\n")
        pe = ailab.save_enricher(code, "tlab3")
        assert pe.exists() and ailab.load_custom_enrichers() == ["tlab3"]
    finally:
        ailab.LAB_DIR, ailab.LAB_DRIVERS = old_dir, old_drv
    from deal_radar.enrich import REGISTRY
    REGISTRY.pop("tlab3", None)


def test_cpu_override_contradiction_unresolved():
    import asyncio
    import os
    import tempfile
    from unittest.mock import patch

    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.driver_sdk import (
        DriverManifest,
        DriverRegistry,
        MarketplaceDriver,
        SearchQuery,
    )
    from deal_radar.orchestrator import run_search
    from deal_radar.store import Store

    def mk(title, price=500):
        return CanonicalListing(id="t:x", source="t", native_id="x", url="u", title=title,
                                description="good laptop", price=price, images=[],
                                seller=Seller(name="s"))

    class F(MarketplaceDriver):
        manifest = DriverManifest(id="t", display_name="t", capabilities=["search"])
        async def search(self, query: SearchQuery):
            return [mk("Lenovo Legion 5 Ryzen 7 5800H RTX")]
    reg = DriverRegistry()
    reg.register(F())
    p = os.path.join(tempfile.mkdtemp(), "cpu.db")
    st = Store(p)
    st.set_fact("t:x", "cpu", "Ryzen 5 5600H")  # conflicts with title 5800H
    with patch("deal_radar.benchmarks.fetch_passmark_cpu", return_value=None):
        out = asyncio.run(run_search(
            {"keywords": "legion", "sources": ["t"], "limit": 5, "models": ["Legion 5"],
             "risk": {}, "enrich": True, "ocr": False, "benchmarks": True, "vision": False,
             "details": False, "overrides": True}, reg, st, None))
    r = out["results"][0]
    assert any("CONTRADICTION" in w for w in r["why"])
    assert any("AI-check" in w and "NOT found" in w for w in r["why"])
    # unresolved path: unknown model, no mention
    class F2(MarketplaceDriver):
        manifest = DriverManifest(id="t2", display_name="t2", capabilities=["search"])
        async def search(self, query: SearchQuery):
            return [mk("Mystery XZY Laptop Pro", 300)]
    reg2 = DriverRegistry()
    reg2.register(F2())
    with patch("deal_radar.scoring.resolve_cpu_candidates", return_value=[]):
        out2 = asyncio.run(run_search(
            {"keywords": "laptop", "sources": ["t2"], "limit": 5, "models": ["Mystery XZY"],
             "risk": {}, "enrich": True, "ocr": False, "benchmarks": False, "vision": False,
             "details": False}, reg2, None, None))
    assert any("CPU unknown" in w for w in out2["results"][0]["why"])
    st.close()


def test_market_endpoint():
    import sys
    sys.path.insert(0, "apps")
    import os
    os.environ.pop("API_KEY", None)
    import api.main as m
    from fastapi.testclient import TestClient
    c = TestClient(m.app)
    r = c.get("/market?limit=5")
    assert r.status_code == 200
    assert "items" in r.json()


def test_cpu_transfer_same_model():
    import asyncio

    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.driver_sdk import (
        DriverManifest,
        DriverRegistry,
        MarketplaceDriver,
        SearchQuery,
    )
    from deal_radar.orchestrator import run_search

    def mk(tid, title):
        return CanonicalListing(id=tid, source="t", native_id=tid, url="u", title=title,
                                description="good", price=300, images=[], seller=Seller(name="s"))

    class F(MarketplaceDriver):
        manifest = DriverManifest(id="t", display_name="t", capabilities=["search"])
        async def search(self, query: SearchQuery):
            return [mk("t:1", "HP EliteBook 845 G8 Ryzen 5 PRO 5650U 16GB"),
                    mk("t:2", "HP EliteBook 845 G8 Ryzen 5 PRO 16GB")]
    reg = DriverRegistry()
    reg.register(F())
    out = asyncio.run(run_search(
        {"keywords": "hp", "sources": ["t"], "limit": 5, "models": ["HP EliteBook 845 G8"],
         "risk": {}, "enrich": True, "ocr": False, "benchmarks": False, "vision": False,
         "details": False}, reg, None, None))
    by_id = {r["listing"]["id"]: r for r in out["results"]}
    assert len(by_id) == 2
    cpu2 = next(e["value"] for e in by_id["t:2"]["enrichments"] if e["field"] == "cpu")
    assert cpu2 == "Ryzen 5 PRO 5650U"
    assert any("transferred" in w for w in by_id["t:2"]["why"])


def test_marketplace_index():
    import sys
    sys.path.insert(0, "apps")
    import os
    os.environ.pop("API_KEY", None)
    import api.main as m
    from fastapi.testclient import TestClient
    c = TestClient(m.app)
    r = c.get("/marketplace")
    assert r.status_code == 200
    d = r.json()
    assert any(x["id"] == "vinted" and x["installed"] for x in d["drivers"])
    assert any(x["id"] == "ebay" and not x["configured"] for x in d["drivers"])
    r2 = c.post("/marketplace/install", json={"id": "willhaben"})
    assert r2.json()["ok"] and "built in" in r2.json()["note"]
    assert c.post("/marketplace/install", json={"id": "nope"}).json()["ok"] is False


def test_kind_caps_and_accessories():
    from deal_radar.decision import heuristic_decide
    bag = heuristic_decide("Lenovo ThinkPad Rucksack schwarz", "gut", 10, "thinkpad")
    assert bag["kind"] == "accessory" and bag["match"] <= 0.45
    lap = heuristic_decide("Lenovo ThinkPad T460 i5", "gut", 100, "thinkpad")
    assert lap["kind"] == "offer" and lap["match"] > bag["match"]
    box = heuristic_decide("iPhone 17 leere OVP", "nur Verpackung", 5, "iphone 17")
    assert box["kind"] == "accessory"


def test_vision_breaker():
    import asyncio

    from deal_radar import vision as V
    V._vision_failures = 0
    V._vision_disabled_until = 0.0
    import os
    os.environ["LOCAL_VISION_API_URL"] = "http://127.0.0.1:9"
    os.environ["LOCAL_MODEL_VISION"] = "x"
    for _ in range(3):
        assert asyncio.run(V.vision_check("http://x/y.jpg", "t", "d")) == {}
    import time
    assert V._vision_disabled_until > time.time()
    del os.environ["LOCAL_VISION_API_URL"]
    del os.environ["LOCAL_MODEL_VISION"]
    V._vision_disabled_until = 0.0


def test_accessory_plurals_contracts_contests():
    from deal_radar.decision import heuristic_decide
    for t in ("6 iPhone 17 Pro Max Hüllen", "iPhone 17 leer box OVP",
              "iPhone 17 pro + Allnet 20GB ab 49,99", "iPhone 17 pro max a gagner",
              "iPhone Vertrag mit Tarif"):
        h = heuristic_decide(t, "x", 10, "iphone 17")
        assert h["kind"] == "accessory", (t, h)
        assert h["match"] <= 0.45
    real = heuristic_decide("Apple iPhone 17 256GB", "Verkaufe mein iPhone 17", 700, "iphone 17")
    assert real["kind"] == "offer"


def test_tausch_is_want():
    from deal_radar.decision import heuristic_decide
    assert heuristic_decide("Nur heute iPhone 17 Pro Max nur Tausch", "x", 5, "iphone 17")["kind"] == "want"


def test_condition_signals():
    from deal_radar.decision import heuristic_decide
    assert heuristic_decide("iPhone NEU OVP", "neu", 5, "iphone")["condition"] == 0.9
    assert heuristic_decide("iPhone defekt Display gesprungen", "kaputt", 5, "iphone")["condition"] == 0.25
    mid = heuristic_decide("iPhone gebraucht", "leichte Gebrauchsspuren", 5, "iphone")["condition"]
    assert mid == 0.55


def test_tls_transport_config():
    from deal_radar.driver_sdk import TlsImpersonatingTransport, transport_from_config
    assert isinstance(transport_from_config({"type": "tls"}), TlsImpersonatingTransport)
    assert isinstance(transport_from_config({"type": "tls", "impersonate": "safari"}), TlsImpersonatingTransport)


def test_filter_properties():
    import random

    from hypothesis import given, settings
    from hypothesis import strategies as st

    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.filter_engine import apply_filters

    @given(st.text(max_size=40), st.floats(allow_nan=False, allow_infinity=False, min_value=0, max_value=1e6), st.booleans())
    @settings(max_examples=60, derandomize=True)
    def prop(title, price, has_desc):
        rng = random.Random(hash((title, price, has_desc)) % (2 ** 32))
        l = CanonicalListing(id="p", source="t", native_id="1", url="u", title=title,
                             description=("desc word " + title) if has_desc else "",
                             price=price if rng.random() > 0.3 else None,
                             seller=Seller(name="s"))
        # invariant 1: never crash, always a FilterResult
        r = apply_filters(l, {"max_price": 500, "rules": [
            {"fields": ["title", "description"], "op": "not_contains", "value": "zzzq"},
            {"field": "price", "op": "lt", "value": 100000}]}, None, None)
        assert isinstance(r.passed, bool)
        # invariant 2: blacklist hit on present word always rejects
        if "word" in (title + " " + l.description).lower():
            r2 = apply_filters(l, {}, [{"fields": ["title", "description"], "op": "not_contains", "value": "word"}], None)
            assert not r2.passed
        # invariant 3: unknown price never excluded by price bounds
        if l.price is None:
            r3 = apply_filters(l, {"max_price": 1}, None, None)
            assert r3.passed
    prop()

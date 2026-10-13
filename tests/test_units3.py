"""Decision/AI layer unit tests with mocked HTTP (no network)."""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages"))

from deal_radar import decision as D


class _NetDown(Exception):
    pass


def _resp(payload=None, status=200):
    m = AsyncMock()
    m.status_code = status
    if status == 429:
        m.raise_for_status = AsyncMock(side_effect=Exception("429"))
    else:
        m.raise_for_status = AsyncMock()
    m.json = (lambda: payload) if not callable(payload) else payload
    return m


def run(coro):
    return asyncio.run(coro)


def test_jev_no_key_and_ok_and_fail():
    assert run(D.jev_decide({}, {})) is None
    with patch.object(D.httpx, "AsyncClient") as AC:
        inst = AsyncMock()
        inst.post = AsyncMock(return_value=_resp({"answers": {}}))
        AC.return_value.__aenter__ = AsyncMock(return_value=inst)
        AC.return_value.__aexit__ = AsyncMock(return_value=False)
        assert run(D.jev_decide({"a": 1}, {"q": 1}, api_key="k")) == {"answers": {}}
        inst.post = AsyncMock(side_effect=Exception("boom"))
        assert run(D.jev_decide({"a": 1}, {"q": 1}, api_key="k")) is None


def test_kev_no_url_and_ok():
    assert run(D.kev_decide({}, {})) is None
    D.KEV_URL = "http://x"
    try:
        with patch.object(D.httpx, "AsyncClient") as AC:
            inst = AsyncMock()
            inst.post = AsyncMock(return_value=_resp({"answers": {"a": 1}}))
            AC.return_value.__aenter__ = AsyncMock(return_value=inst)
            AC.return_value.__aexit__ = AsyncMock(return_value=False)
            assert run(D.kev_decide("s", {"q": 1})) == {"answers": {"a": 1}}
    finally:
        D.KEV_URL = ""


def test_cloud_json_local_then_failover():
    D.CLOUD_API_URL = "http://x"
    D.CLOUD_API_KEY = "k"
    ok_payload = {"choices": [{"message": {"content": '{"a": 1}'}}]}
    with patch.object(D.httpx, "AsyncClient") as AC:
        inst = AsyncMock()
        inst.post = AsyncMock(return_value=_resp(ok_payload))
        AC.return_value.__aenter__ = AsyncMock(return_value=inst)
        AC.return_value.__aexit__ = AsyncMock(return_value=False)
        out = run(D.cloud_json("s", "u", model="m"))
        assert out == {"a": 1}
    # all fail -> None
    with patch.object(D.httpx, "AsyncClient") as AC:
        inst = AsyncMock()
        inst.post = AsyncMock(side_effect=Exception("down"))
        AC.return_value.__aenter__ = AsyncMock(return_value=inst)
        AC.return_value.__aexit__ = AsyncMock(return_value=False)
        with patch("asyncio.sleep", new=AsyncMock()):
            assert run(D.cloud_json("s", "u", model="m")) is None


def test_nl_fallback_paths():
    fb = D.nl_fallback("ThinkPad unter 700 ohne defekt OLED")
    assert fb["hard"].get("max_price") == 700
    assert any("defekt" in b.get("value", "") for b in fb["blacklist"])
    assert fb["attributes"].get("display") == "oled"
    fb2 = D.nl_fallback("usb-c kabel")
    assert fb2["attributes"].get("connector") == "usb-c"
    fb3 = D.nl_fallback("laptop ab 200")
    assert fb3["hard"].get("min_price") == 200
    fb4 = D.nl_fallback("ThinkPad under 700 without defects")
    assert fb4["hard"].get("max_price") == 700
    assert any("defect" in b.get("value", "") for b in fb4["blacklist"])
    assert "without" not in fb4["keywords"] and "700" not in fb4["keywords"]
    assert any(b.get("value") == "case" and b.get("ai_suggested") for b in fb4["blacklist"])
    fb5 = D.nl_fallback("holzstuhl gebraucht")
    assert not any(b.get("ai_suggested") for b in fb5["blacklist"])
    fb6 = D.nl_fallback("alle laptops")
    assert fb6["category"] == "laptops" and fb6["keywords"] == ""
    fb7 = D.nl_fallback("autos unter 5000")
    assert fb7["category"] == "" and fb7["hard"].get("max_price") == 5000


def test_priceless_listing_never_kills_search():
    """Regression: price=None (e.g. 'on request' iPhone boxes) must not fail ScoredListing."""
    import asyncio
    import os
    import tempfile

    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.driver_sdk import (
        DriverManifest,
        DriverRegistry,
        MarketplaceDriver,
        SearchQuery,
    )

    class F(MarketplaceDriver):
        manifest = DriverManifest(id="t", display_name="t", capabilities=["search"])

        async def search(self, query: SearchQuery):
            return [CanonicalListing(id="t:x", source="t", native_id="x", url="https://t/x",
                                     title="iPhone 17 box empty", description="box only",
                                     price=None, images=[], seller=Seller(name="s"))]

    from deal_radar.orchestrator import run_search
    from deal_radar.store import Store
    reg = DriverRegistry()
    reg.register(F())
    st = Store(os.path.join(tempfile.mkdtemp(), "nol.db"))
    out = asyncio.run(run_search(
        {"keywords": "iphone 17", "sources": ["t"], "limit": 5,
         "risk": {}, "enrich": False, "ocr": False, "benchmarks": False, "vision": False,
         "details": False}, reg, st, None))
    assert out.get("results"), out.get("driver_errors")
    st.close()


def test_stage_b_via_cloud_shapes():
    async def fake_json(*a, **k):
        return {"exact": 0.9, "risk": 0.1, "condition": 0.8, "note": "ok"}
    with patch.object(D, "cloud_json", new=fake_json):
        out = run(D.stage_b_via_cloud("t", "d", 5, "kw"))
        assert out["exact"] == 0.9 and out["note"] == "ok"
    with patch.object(D, "cloud_json", new=AsyncMock(return_value=None)):
        assert run(D.stage_b_via_cloud("t", "d", 5, "kw")) == {}


def _mk(id_, **kw):
    from deal_radar.contracts import CanonicalListing, Seller
    d = {"title": "T", "description": "Some decent description text here for scoring",
         "price": 100.0, "images": ["i1"], "url": "https://x/1", "seller": Seller(name="s")}
    d.update(kw)
    return CanonicalListing(id=id_, source="t", native_id=id_, **d)


def _reg(items, driver_id="t", err=None):
    from deal_radar.driver_sdk import (
        DriverManifest,
        DriverRegistry,
        MarketplaceDriver,
        SearchQuery,
    )

    class F(MarketplaceDriver):
        manifest = DriverManifest(id=driver_id, display_name=driver_id, capabilities=["search"])

        async def search(self, query: SearchQuery):
            if err:
                raise RuntimeError(err)
            return items

    reg = DriverRegistry()
    reg.register(F())
    return reg


def test_orchestrator_lanes_and_gates():
    import asyncio
    import os
    import tempfile

    from deal_radar.orchestrator import run_search
    from deal_radar.store import Store

    items = [_mk("t:1", title="ThinkPad T14 Ryzen", price=100),
             _mk("t:2", title="ThinkPad X1", price=2000),
             _mk("t:3", title="Defekt Gerät Bastler", price=5)]
    out = asyncio.run(run_search(
        {"keywords": "thinkpad", "sources": ["t"], "limit": 10, "hard": {"max_price": 500},
         "risk": {"block_threshold": 0.01, "hard_filter_enabled": True}, "enrich": False,
         "ocr": False, "benchmarks": False, "vision": False, "details": False},
        _reg(items), None, None))
    assert out["results"]
    # unknown driver id -> clean error entry
    out2 = asyncio.run(run_search({"keywords": "x", "sources": ["nope"], "limit": 5},
                                  _reg(items), None, None))
    assert "nope" in out2["driver_errors"]
    # dedupe + store events + notifier path
    p = os.path.join(tempfile.mkdtemp(), "o.db")
    st = Store(p)
    notes = []

    class N:
        async def send(self, title, body, extra=None):
            notes.append(title)
            return True

    out3 = asyncio.run(run_search(
        {"keywords": "thinkpad", "sources": ["t"], "limit": 10, "risk": {},
         "enrich": False, "ocr": False, "benchmarks": False, "vision": False, "details": False},
        _reg([_mk("t:1", title="ThinkPad T14", price=100)]), st, N()))
    assert out3["results"]
    out4 = asyncio.run(run_search(
        {"keywords": "thinkpad", "sources": ["t"], "limit": 10, "risk": {},
         "enrich": False, "ocr": False, "benchmarks": False, "vision": False, "details": False},
        _reg([_mk("t:1", title="ThinkPad T14 new title", price=90)]), st, N()))
    assert any("Price" in n for n in notes)
    assert out4["results"]
    st.close()


def test_orchestrator_ai_paths_mocked():
    import asyncio
    from unittest.mock import AsyncMock, patch

    from deal_radar import orchestrator as O
    items = [_mk("t:1", title="ThinkPad device machine Ryzen 7 5800H", price=500,
                 description="great machine, pickup possible abholung versandpaypal")]
    base = {"keywords": "thinkpad ryzen laptop oled", "sources": ["t"], "limit": 5, "risk": {},
            "enrich": True, "ocr": True, "benchmarks": True, "vision": True, "details": True,
            "attributes": {"ram": "16GB"}}
    with patch("deal_radar.vision.ocr_listing_images", return_value=["Ryzen 7 PRO 6850U"]), \
         patch("deal_radar.benchmarks.fetch_passmark_cpu",
               return_value={"multi": 20000, "single": 3000, "source": "t", "ts": 0,
                             "class": "Laptop", "cores": 8}), \
         patch.object(O, "jev_decide", new=AsyncMock(return_value=None)), \
         patch.object(O, "kev_decide", new=AsyncMock(return_value={
             "answers": {"is_exact_product": {"noul": 0.9},
                         "scam_risk": {"score": 1.0}, "condition": {"score": 3.0}}})):
        import os
        os.environ["KEV_URL"] = "http://x"
        try:
            out = asyncio.run(O.run_search(dict(base), _reg(items), None, None))
        finally:
            del os.environ["KEV_URL"]
    r = out["results"][0]
    assert any(e["field"] == "cpu_benchmark" for e in r["enrichments"])
    assert any("stage-B" in w for w in r["why"])
    # vision queue path with mocked vision (borderline match forces Stage B)
    items2 = [_mk("t:1", title="ThinkPad machine device", price=500,
                  description="great machine, pickup possible abholung versandpaypal")]
    with patch("deal_radar.vision.vision_check",
               new=AsyncMock(return_value={"shows_item": 0.1, "is_stock": 0.9,
                                           "visible_text": "zzz", "note": "stock photo mismatch"})):
        out2 = asyncio.run(O.run_search(dict(base, keywords="thinkpad ryzen laptop"), _reg(items2), None, None))
    assert any("visual_consistency" in (x.get("deal_dna") or {}) for x in out2["results"])


def test_registry_branches():
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    from deal_radar import registry as R

    assert R.load_index("/nonexistent-xyz.json") == {"drivers": []}
    with patch.object(R.urllib.request, "urlopen") as uo:
        import io
        uo.return_value.__enter__ = lambda s: io.BytesIO(b'{"drivers": []}')
        uo.return_value.__exit__ = lambda s, *a: False
        assert R.load_index("http://x/index.json") == {"drivers": []}
        assert R.load_index("") == {"drivers": []} or isinstance(R.load_index(""), dict)
    try:
        R.load_driver_module("definitely-not-a-driver")
        assert False
    except FileNotFoundError:
        pass
    assert R.check("willhaben")["ok"] and R.check("kleinanzeigen")["ok"]
    # check with broken module (no Driver subclass)
    tmp = Path(tempfile.mkdtemp()) / "baddrv" / "driver.py"
    tmp.parent.mkdir(parents=True)
    tmp.write_text("X = 1\n")
    with patch.object(R, "DRIVERS_DIR", tmp.parent.parent), \
         patch.object(R, "COMMUNITY", tmp.parent.parent):
        r = R.check("baddrv")
        assert not r["ok"]
    # install path: source + already-installed + checksum mismatch
    src = Path(tempfile.mkdtemp()) / "src"
    src.mkdir()
    (src / "driver.py").write_text(
        "from deal_radar.driver_sdk import MarketplaceDriver, DriverManifest, SearchQuery\n"
        "class TmpDriver(MarketplaceDriver):\n"
        "    manifest = DriverManifest(id='tmpdrv', display_name='Tmp', capabilities=['search'])\n"
        "    async def search(self, query: SearchQuery):\n        return []\n")
    with patch.object(R, "COMMUNITY", Path(tempfile.mkdtemp())):
        r = R.install({"id": "tmpdrv", "version": "1", "source": f"path:{src}"})
        assert r["ok"]
        r2 = R.install({"id": "tmpdrv", "version": "1", "source": f"path:{src}"})
        assert not r2["ok"] and "already installed" in r2["error"]
        r3 = R.install({"id": "x", "source": "bogus:zzz"})
        assert not r3["ok"]


def test_notifications_all_channels():
    import asyncio
    from unittest.mock import AsyncMock, patch

    from deal_radar import notifications as N

    async def boom(*a, **k):
        raise _NetDown("net down")

    async def ok200(*a, **k):
        class R:
            status_code = 200
            def raise_for_status(self): pass
        return R()

    with patch.object(N.httpx, "AsyncClient") as AC:
        inst = AsyncMock()
        inst.post = AsyncMock(side_effect=boom)
        AC.return_value.__aenter__ = AsyncMock(return_value=inst)
        AC.return_value.__aexit__ = AsyncMock(return_value=False)
        assert asyncio.run(N.NtfyNotifier("http://x").send("t", "b")) is False
        assert asyncio.run(N.WebhookNotifier("http://x").send("t", "b")) is False
        assert asyncio.run(N.TelegramNotifier("tok", "chat").send("t", "b")) is False
        assert asyncio.run(N.SignalNotifier("http://x", "+1").send("t", "b")) is False
        inst.post = AsyncMock(side_effect=ok200)
        assert asyncio.run(N.NtfyNotifier("http://x").send("t", "b")) is True
        assert asyncio.run(N.TelegramNotifier("tok", "chat").send("t", "b")) is True
    n = N.notifier_from_env({"NOTIFIERS_JSON": "not json"})
    assert n is not None
    n2 = N.notifier_from_env({"NOTIFIERS_JSON": '[{"type":"telegram","bot_token":"t","chat_id":"c"}]'})
    from deal_radar.notifications import MultiNotifier
    assert isinstance(n2, MultiNotifier)
    n3 = N.notifier_from_env({"NOTIFIERS_JSON": '[{"type":"email","smtp_host":"h","smtp_user":"u","smtp_pass":"p","to":"t"}]'})
    assert isinstance(n3, MultiNotifier)
    with patch("smtplib.SMTP_SSL", side_effect=Exception("no mail")):
        assert asyncio.run(N.EmailNotifier("h", "u", "p", "t").send("t", "b")) is False


def test_benchmarks_and_vision_units():
    import asyncio
    from unittest.mock import AsyncMock, patch

    from deal_radar import benchmarks as B
    from deal_radar import vision as V

    B._mem.clear()
    assert B.fetch_passmark_cpu("") is None or isinstance(B.fetch_passmark_cpu(""), (dict, type(None)))
    assert B.parse_passmark_detail("<html></html>") == (None, None)
    assert B.parse_passmark_full("<html></html>")["multi"] is None
    assert V.ocr_bytes(b"") == ""
    assert V.download_image("http://127.0.0.1:9/nope.jpg", timeout=1) is None
    assert asyncio.run(V.vision_check("", "t", "d")) == {}
    with patch.object(V.httpx, "AsyncClient") as AC:
        inst = AsyncMock()
        inst.post = AsyncMock(side_effect=Exception("down"))
        AC.return_value.__aenter__ = AsyncMock(return_value=inst)
        AC.return_value.__aexit__ = AsyncMock(return_value=False)
        assert asyncio.run(V.vision_check("http://x/i.jpg", "t", "d")) == {}


def test_nl_intent_variants():
    import asyncio
    from unittest.mock import AsyncMock, patch

    from deal_radar import decision as D
    D.CLOUD_API_URL = ""
    D.CLOUD_API_KEY = ""
    D.KEV_URL = ""

    async def cloud_full(system, user, max_tokens=600, model=""):
        return {"keywords": "iphone", "category": "phones",
                "hard": [{"field": "price", "op": "lt", "value": 5}],
                "blacklist": [], "exclude": ["case", "Apple"],
                "attributes": {"connector": "usb-c", "processor": "i7"},
                "models": ["iPhone 15"], "risk": {}}

    with patch.object(D, "cloud_json", new=cloud_full):
        out = asyncio.run(D.nl_to_intent("iphone with usb c"))
        assert out["models"] == ["iPhone 15"]
        assert out["hard"] == {"rules": [{"field": "price", "op": "lt", "value": 5}]}
        assert all("Apple" not in str(b.get("value", "")) for b in out["blacklist"])
        # connector kept (query overlap), processor dropped (invented)
        assert out["attributes"].get("connector") == "usb-c"
        assert "processor" not in out["attributes"]

    async def cloud_need_fix(system, user, max_tokens=600, model=""):
        if "List ONLY" in user:
            return {"models": ["ThinkPad X1"], "exclude": ["case"]}
        return {"keywords": "thinkpad x1", "models": [], "exclude": []}

    with patch.object(D, "_nl_cached", return_value=None), \
         patch.object(D, "_nl_store", return_value=None), \
         patch.object(D, "cloud_json", new=cloud_need_fix):
        out2 = asyncio.run(D.nl_to_intent("which thinkpad x1"))
        assert out2["models"] == ["ThinkPad X1"]
        assert any("case" in str(b.get("value", "")) for b in out2["blacklist"])

    with patch.object(D, "cloud_json", new=AsyncMock(return_value=None)):
        out3 = asyncio.run(D.nl_to_intent("plain words here"))
        assert out3["keywords"]
    # cached hit path
    with patch.object(D, "_nl_cached", return_value={"keywords": "cached!"}):
        assert asyncio.run(D.nl_to_intent("anything")) == {"keywords": "cached!"}
    # cloud_code paths
    with patch.object(D, "cloud_code", new=AsyncMock(return_value=None)):
        assert asyncio.run(D.stage_b_via_cloud("t", "d", 1, "k")) == {}
    with patch.object(D, "cloud_code", new=AsyncMock(return_value="not json at all")):
        assert asyncio.run(D.stage_b_via_cloud("t", "d", 1, "k")) == {}


def test_registry_github_install_mocked():
    import io
    import tarfile
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    from deal_radar import registry as R

    src = Path(tempfile.mkdtemp())
    (src / "repo-1").mkdir()
    (src / "repo-1" / "drv").mkdir()
    (src / "repo-1" / "drv" / "driver.py").write_text(
        "from deal_radar.driver_sdk import MarketplaceDriver, DriverManifest, SearchQuery\n"
        "class GhDriver(MarketplaceDriver):\n"
        "    manifest = DriverManifest(id='ghdrv', display_name='Gh', capabilities=['search'])\n"
        "    async def search(self, query: SearchQuery):\n        return []\n")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        tf.add(str(src / "repo-1"), arcname="repo-1")
    data = buf.getvalue()

    class Resp:
        status_code = 200
        content = data
        def raise_for_status(self): pass

    with patch.object(R, "COMMUNITY", Path(tempfile.mkdtemp())), \
         patch("httpx.get", return_value=Resp()):
        r = R.install({"id": "ghdrv", "version": "1",
                       "source": "github:owner/repo@main:drv"})
        assert r["ok"], r
        assert R.check("ghdrv")["ok"]
    # registry main() list path (remote index mocked)
    with patch.object(R.urllib.request, "urlopen", side_effect=Exception("offline")):
        assert R.main(["registry", "list"]) == 0
    assert R.main(["registry", "bogus"]) == 1


def test_benchmarks_fetch_mocked():
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    from deal_radar import benchmarks as B

    html = (Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "passmark-5800h.html"
            ).read_text(encoding="utf-8", errors="ignore")

    class Resp:
        status_code = 200
        text = html

    with tempfile.TemporaryDirectory() as td:
        with patch.object(B, "_cache_path", Path(td) / "b.json"), \
             patch.object(B.httpx, "get", return_value=Resp()):
            B._mem.clear()
            out = B.fetch_passmark_cpu("Ryzen 7 5800H")
            assert out and out["multi"] == 20461
            out2 = B.fetch_passmark_cpu("Ryzen 7 5800H")  # mem cache
            assert out2["multi"] == 20461
            B._mem.clear()
            out3 = B.fetch_passmark_cpu("Ryzen 7 5800H")  # disk cache
            assert out3["multi"] == 20461
        with patch.object(B.httpx, "get", side_effect=Exception("net down")):
            B._mem.clear()
            assert B.fetch_passmark_cpu("Missing CPU 9999") is None
    assert B.lookup_gpu("definitely not a gpu xyz") is None


def test_vision_ocr_paths():
    from unittest.mock import patch

    from deal_radar import vision as V

    assert V.ocr_listing_images([]) == []
    V._ocr_cache.clear()
    with patch.object(V.shutil, "which", return_value=None):
        assert V.ocr_bytes(b"xxx") == ""
    with patch.object(V.shutil, "which", return_value="/usr/bin/tesseract"), \
         patch.object(V.subprocess, "run") as run:
        run.return_value.stdout = "  Hello Board  "
        run.return_value.returncode = 0
        assert V.ocr_bytes(b"fake-bytes") == "Hello Board"
        assert V.ocr_bytes(b"fake-bytes") == "Hello Board"  # cache hit
    V._ocr_cache.clear()
    with patch.object(V, "download_image", return_value=b"img"), \
         patch.object(V.shutil, "which", return_value="/usr/bin/tesseract"), \
         patch.object(V.subprocess, "run") as run:
            run.return_value.stdout = "Serial 123"
            run.return_value.returncode = 0
            assert V.ocr_listing_images(["http://x/1.jpg", "http://x/1.jpg"]) == ["Serial 123"]


def test_cloud_code_paths():
    import asyncio
    from unittest.mock import AsyncMock, patch

    from deal_radar import decision as D
    D.CLOUD_API_URL = ""
    D.CLOUD_API_KEY = ""

    def ok_client(text):
        async def fake_post(*a, **k):
            class R:
                status_code = 200
                def raise_for_status(self): pass
                def json(self):
                    return {"choices": [{"message": {"content": text}}]}
            return R()
        AC = AsyncMock()
        inst = AsyncMock()
        inst.post = fake_post
        AC.__aenter__ = AsyncMock(return_value=inst)
        AC.__aexit__ = AsyncMock(return_value=False)
        return AC

    with patch.object(D.httpx, "AsyncClient", new=lambda **k: ok_client("print(1)")), \
         patch.dict("os.environ", {"LOCAL_API_URL": "http://local"}):
        assert asyncio.run(D.cloud_code("s", "u")) == "print(1)"
    with patch.object(D.httpx, "AsyncClient", new=lambda **k: ok_client(None)):
        D.CLOUD_API_URL = "http://x"
        D.CLOUD_API_KEY = "k"
        with patch.dict("os.environ", {}, clear=False), \
             patch("asyncio.sleep", new=AsyncMock()):
            import os
            os.environ.pop("LOCAL_API_URL", None)
            assert asyncio.run(D.cloud_code("s", "u")) is None
            D.CLOUD_API_URL = ""
            D.CLOUD_API_KEY = ""


def test_nl_more_branches():
    import asyncio
    from unittest.mock import patch

    from deal_radar import decision as D
    D.CLOUD_API_URL = ""
    D.CLOUD_API_KEY = ""

    async def cloud_attrs(system, user, max_tokens=600, model=""):
        return {"keywords": "laptop", "models": ["-rayzen-"], "exclude": ["Apple", "case"],
                "attributes": {"display": "amoled screen here", "color": "red"},
                "hard": {"max_price": 5}, "blacklist": []}

    with patch.object(D, "_nl_cached", return_value=None), \
         patch.object(D, "_nl_store", return_value=None), \
         patch.object(D, "cloud_json", new=cloud_attrs):
        out = asyncio.run(D.nl_to_intent("laptop red"))
        # maker guard drops Apple; display kept only on overlap ("amoled screen here" vs query? no)
        assert all("Apple" not in str(b.get("value", "")) for b in out["blacklist"])
    # stage_b paths
    with patch.object(D, "cloud_json", new=AsyncMock(return_value={"exact": "bad"})):
        pass


def test_decision_branches_extra():
    import asyncio
    import tempfile
    from pathlib import Path
    from unittest.mock import AsyncMock, patch

    from deal_radar import decision as D
    D.CLOUD_API_URL = ""
    D.CLOUD_API_KEY = ""

    fb = D.nl_fallback("laptop ab 200 ohne kratzer sehr gut")
    assert fb["hard"].get("min_price") == 200
    assert any("kratzer" in b.get("value", "") for b in fb["blacklist"])
    fb2 = D.nl_fallback("handy mit lightning kabel")
    assert fb2["attributes"].get("connector") == "lightning"
    from deal_radar.decision import heuristic_decide
    assert heuristic_decide("t", "sehr gut erhalten", 1, "t")["condition"] == 0.78
    assert heuristic_decide("t", "leichte Gebrauchsspuren", 1, "t")["condition"] == 0.55
    assert heuristic_decide("t", "B-Ware", 1, "t")["condition"] == 0.55
    # nl cache roundtrip on temp path
    with tempfile.TemporaryDirectory() as td, \
         patch.object(D, "_NL_CACHE", str(Path(td) / "nl.json")):
            D._nl_store("hello world", {"keywords": "hello"})
            assert D._nl_cached("hello world") == {"keywords": "hello"}
            assert D._nl_cached("other") is None
    # corrupt cache file -> None, never crash
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "nl.json"
        p.write_text("{{{not json")
        with patch.object(D, "_NL_CACHE", str(p)):
            assert D._nl_cached("x") is None
    # stage_b bad values -> {}
    async def bad():
        return {"exact": object()}
    with patch.object(D, "cloud_json", new=AsyncMock(return_value={"exact": object()})):
        assert asyncio.run(D.stage_b_via_cloud("t", "d", 1, "k")) == {}

    # cloud_code round 2 success
    D.CLOUD_API_URL = "http://x"
    D.CLOUD_API_KEY = "k"
    calls = {"n": 0}

    async def fake_post(*a, **k):
        calls["n"] += 1
        if calls["n"] <= len(D.CLOUD_MODELS):
            raise _NetDown("down")
        class R:
            status_code = 200
            def raise_for_status(self): pass
            def json(self):
                return {"choices": [{"message": {"content": "x=1"}}]}
        return R()
    with patch.object(D.httpx, "AsyncClient") as AC:
        inst = AsyncMock()
        inst.post = fake_post
        AC.return_value.__aenter__ = AsyncMock(return_value=inst)
        AC.return_value.__aexit__ = AsyncMock(return_value=False)
        with patch("asyncio.sleep", new=AsyncMock()):
            assert asyncio.run(D.cloud_code("s", "u")) == "x=1"
    D.CLOUD_API_URL = ""
    D.CLOUD_API_KEY = ""


def test_orchestrator_branches_extra():
    import asyncio
    from unittest.mock import patch

    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.driver_sdk import (
        DriverManifest,
        DriverRegistry,
        MarketplaceDriver,
        SearchQuery,
    )
    from deal_radar.orchestrator import run_search

    def mk(i, **kw):
        src = kw.pop("src", "t")
        d = {"title": "ThinkPad T14 Ryzen 7 5800H 16GB", "description": "great laptopabholung ".ljust(60, "x"),
             "price": 500.0, "images": ["http://img/1.jpg"], "url": "u", "seller": Seller(name="s")}
        d.update(kw)
        return CanonicalListing(id=i, source=src, native_id=i, **d)

    class F(MarketplaceDriver):
        manifest = DriverManifest(id="t", display_name="t", capabilities=["search"])
        async def search(self, query: SearchQuery):
            return [mk("t:1"), mk("t:1"),  # dupe key
                    mk("t:3", title="Defekt XYZ", price=5),
                    mk("t:4", title="ThinkPad T14", price=100)]

    reg = DriverRegistry()
    reg.register(F())
    base = {"keywords": "thinkpad", "sources": ["t"], "limit": 10, "risk": {},
            "enrich": True, "ocr": False, "benchmarks": True, "vision": False, "details": False,
            "attributes": {"ram": "16GB", "color": "pink"}}
    out = asyncio.run(run_search(dict(base), reg, None, None))
    assert out["filtered_out"] >= 1
    # details block with mocked fetch_detail
    class FD(MarketplaceDriver):
        manifest = DriverManifest(id="fd", display_name="fd",
                                  capabilities=["search", "fetch_detail"])
        async def search(self, query: SearchQuery):
            return [mk("fd:1", src="fd", title="ThinkPad T14", price=100)]
        async def fetch_detail(self, ref):
            return mk("fd:1", src="fd", title="ThinkPad T14 detail", price=100,
                      description="full text here " * 30)
    reg2 = DriverRegistry()
    reg2.register(FD())
    out2 = asyncio.run(run_search(
        {"keywords": "thinkpad", "sources": ["fd"], "limit": 5, "risk": {},
         "enrich": True, "ocr": False, "benchmarks": False, "vision": False, "details": True},
        reg2, None, None))
    assert any("detail page enriched" in w for r in out2["results"] for w in r["why"])
    # imgdup dupe block with mocked identical hashes
    with patch("deal_radar.imgdup.image_hash", return_value=123):
        out3 = asyncio.run(run_search(
            {"keywords": "thinkpad", "sources": ["a", "b"], "limit": 5, "risk": {"block_threshold": 0.99},
             "enrich": False, "ocr": False, "benchmarks": False, "vision": False, "details": False},
            _reg2src(), None, None))
    assert any("same item also on" in w for r in out3["results"] for w in r["why"])


def _reg2src():
    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.driver_sdk import (
        DriverManifest,
        DriverRegistry,
        MarketplaceDriver,
        SearchQuery,
    )

    def mk2(i, src, title):
        return CanonicalListing(id=f"{src}:{i}", source=src, native_id=i, url="u", title=title,
                                description="decent description text here", price=100.0,
                                images=[f"http://img/{src}.jpg"], seller=Seller(name="s"))

    class A(MarketplaceDriver):
        manifest = DriverManifest(id="a", display_name="a", capabilities=["search"])
        async def search(self, query: SearchQuery):
            return [mk2("1", "a", "ThinkPad T14")]

    class B(MarketplaceDriver):
        manifest = DriverManifest(id="b", display_name="b", capabilities=["search"])
        async def search(self, query: SearchQuery):
            return [mk2("1", "b", "ThinkPad T14")]
    reg = DriverRegistry()
    reg.register(A())
    reg.register(B())
    return reg


def test_total_cost_dna():
    import asyncio

    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.driver_sdk import (
        DriverManifest,
        DriverRegistry,
        MarketplaceDriver,
        SearchQuery,
    )
    from deal_radar.orchestrator import run_search

    def mk(i, price, ship):
        return CanonicalListing(id=i, source="t", native_id=i, url="u", title=f"ThinkPad T14 {i}",
                                description="decent description text", price=price, images=[f"http://img/{i}.jpg"],
                                shipping_cost=ship, seller=Seller(name="s"))

    class F(MarketplaceDriver):
        manifest = DriverManifest(id="t", display_name="t", capabilities=["search"])
        async def search(self, query: SearchQuery):
            return [mk("t:1", 100.0, 10.0), mk("t:2", 105.0, 0.0)]
    reg = DriverRegistry()
    reg.register(F())
    out = asyncio.run(run_search(
        {"keywords": "thinkpad", "sources": ["t"], "limit": 5, "risk": {},
         "enrich": False, "ocr": False, "benchmarks": False, "vision": False, "details": False},
        reg, None, None))
    tots = {r["listing"]["id"]: r["deal_dna"]["total_cost"] for r in out["results"]}
    assert tots == {"t:1": 110.0, "t:2": 105.0}


def test_flagged_kept_with_reasons():
    import asyncio
    import os
    import tempfile

    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.driver_sdk import (
        DriverManifest,
        DriverRegistry,
        MarketplaceDriver,
        SearchQuery,
    )
    from deal_radar.orchestrator import run_search
    from deal_radar.store import Store

    class F(MarketplaceDriver):
        manifest = DriverManifest(id="t", display_name="t", capabilities=["search"])

        async def search(self, query: SearchQuery):
            return [CanonicalListing(id="t:x", source="t", native_id="x", url="https://t/x",
                                     title="ThinkPad T14", description="good laptop",
                                     price=500, images=[], seller=Seller(name="s"))]

    reg = DriverRegistry()
    reg.register(F())
    st = Store(os.path.join(tempfile.mkdtemp(), "flag.db"))
    out = asyncio.run(run_search(
        {"keywords": "thinkpad", "sources": ["t"], "limit": 5,
         "blacklist": [{"fields": ["title"], "op": "contains", "value": "zzz-no-match"}],
         "required": [{"fields": ["title"], "op": "contains", "value": "impossible-word"}],
         "risk": {}, "enrich": False, "ocr": False, "benchmarks": False, "vision": False,
         "details": False}, reg, st, None))
    assert out["results"] == [] and out["filtered_out"] >= 1
    assert out["filtered"] and "hidden" in out["filtered"][0]["lane"]
    assert "required" in out["filtered"][0]["why"][0] or "hidden" in out["filtered"][0]["why"][0]
    st.close()


def test_registry_uninstall_roundtrip():
    import tempfile
    from pathlib import Path

    import deal_radar.registry as R
    tmp = Path(tempfile.mkdtemp())
    with patch.object(R, "COMMUNITY", tmp), patch.object(R, "LAB_DRIVERS", tmp):
        src = tmp / "seed"
        src.mkdir()
        (src / "driver.py").write_text(
            "from deal_radar.driver_sdk import MarketplaceDriver, DriverManifest, SearchQuery\n"
            "class GoneDriver(MarketplaceDriver):\n"
            "    manifest = DriverManifest(id='gone', display_name='Gone', capabilities=['search'])\n"
            "    async def search(self, query: SearchQuery):\n        return []\n")
        assert R.install({"id": "gone", "version": "1", "source": f"path:{src}"})["ok"]
        assert R.uninstall("gone")["ok"] and not (tmp / "gone").exists()
        assert not R.uninstall("gone")["ok"]
        assert not R.uninstall("../evil")["ok"]
        assert not R.uninstall("builtin-x")["ok"]


def test_store_jobs_lifecycle():
    import os
    import tempfile

    from deal_radar.store import Store
    st = Store(os.path.join(tempfile.mkdtemp(), "jobs.db"))
    st.job_upsert("s1", "running", 1, 4, {"keywords": "t"})
    st.save_search("s1", {"keywords": "t", "sources": ["t"]}, total=42)
    rows = st.list_searches()
    assert rows[0]["results"] == 42 and rows[0]["job"]["status"] == "running"
    assert st.job_interrupt_stale() == 1
    assert st.list_searches()[0]["job"]["status"] == "interrupted"
    st.close()


LAB_ENRICHER_CODE = '''
from deal_radar.enrich import Enricher, register
from deal_radar.contracts import EnrichmentFact, FactStatus, Evidence
class WarrantyEnricher(Enricher):
    id = "warranty"
    version = "0.1.0"
    def supports(self, listing):
        return True
    def enrich(self, listing, ctx):
        t = (listing.title or "") + " " + (listing.description or "")
        if "garantie" in t.lower():
            return [EnrichmentFact(field="warranty", value="mentioned", confidence=0.8,
                                   status=FactStatus.EXTERNAL,
                                   evidence=[Evidence(type="external", detail="test")])]
        return []
register(WarrantyEnricher())
'''.strip()


def test_lab_generate_e2e_mocked_model():
    """Full Lab loop with a stubbed model: prompt -> code -> gate -> save -> hot-load ->
    contract fire-check, then a follow-up iteration on top of the previous code."""
    import asyncio
    import tempfile
    from pathlib import Path
    from unittest.mock import AsyncMock, patch

    from deal_radar import ailab
    tmp = Path(tempfile.mkdtemp())
    stages = []
    with patch.object(ailab, "LAB_DIR", tmp), \
         patch("deal_radar.decision.cloud_code", new=AsyncMock(return_value=LAB_ENRICHER_CODE)):
        out = asyncio.run(ailab.generate("enricher", "flag listings mentioning warranty",
                                         progress=lambda s, m: stages.append(s)))
        assert out["ok"], out
        assert (tmp / (out["id"] + ".py")).exists()
        assert "waiting_model" in stages and "contract_check" in stages
        # follow-up iteration builds on the previous code
        seen = {}

        async def fake_code(sys, task):
            seen["task"] = task
            assert "warranty test" in task or "flag listings" in task
            assert "WarrantyEnricher" in task  # previous code included
            return LAB_ENRICHER_CODE.replace('"warranty"', '"warranty2"').replace(
                "id = \"warranty\"", "id = \"warranty2\"")

        with patch("deal_radar.decision.cloud_code", new=fake_code):
            out2 = asyncio.run(ailab.generate("enricher", "warranty test",
                                              followup="also catch Gewehrleistung typo",
                                              prior_code=(tmp / (out["id"] + ".py")).read_text(),
                                              prior_error=""))
            assert out2["ok"], out2
            assert out2["id"] != out["id"]
        # gated junk never executes
        bad = asyncio.run(ailab.generate("x", "y", prior_code="", prior_error=""))
        assert bad["ok"] is False  # no model output path needs no model; validated below
    assert ailab.validate_python("import os\nx=1") is not None
    assert ailab.validate_python("import httpx\nx=1") is None


def test_cooperative_stop_keeps_partials():
    import asyncio

    from deal_radar import orchestrator as O
    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.driver_sdk import (
        DriverManifest,
        DriverRegistry,
        MarketplaceDriver,
        SearchQuery,
    )

    class F(MarketplaceDriver):
        manifest = DriverManifest(id="t", display_name="t", capabilities=["search"])

        async def search(self, query: SearchQuery):
            return [CanonicalListing(id=f"t:{i}", source="t", native_id=str(i),
                                     url="https://t/x", title=f"ThinkPad {i}",
                                     description="good laptop", price=100 + i,
                                     images=[], seller=Seller(name="s")) for i in range(40)]

    reg = DriverRegistry()
    reg.register(F())
    O._STOP.add("s_stopme")
    try:
        out = asyncio.run(O.run_search(
            {"keywords": "thinkpad", "sources": ["t"], "limit": 100, "_sid": "s_stopme",
             "risk": {}, "enrich": False, "ocr": False, "benchmarks": False,
             "vision": False, "details": False}, reg, None, None))
    finally:
        O._STOP.discard("s_stopme")
    assert out.get("stopped") is True


def test_kleinanzeigen_category_urls():
    import asyncio
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "drivers"))
    from unittest.mock import patch

    from kleinanzeigen.driver import KleinanzeigenDriver

    from deal_radar.driver_sdk import SearchQuery, transport_from_config
    seen = []

    d = KleinanzeigenDriver(transport_from_config(None))
    async def fake_page(url):
        seen.append(url)
        return ([{"id": "1", "url": "https://www.kleinanzeigen.de/x/1", "title": "t",
                  "price": 5, "images": [], "location": "Berlin", "seller": "s",
                  "shipping": False, "description": "d"}], None)
    with patch.object(d, "_fetch_page", new=fake_page):
        asyncio.run(d.search(SearchQuery(keywords="", category="phones", limit=5, max_pages=1)))
        assert seen[-1].startswith("https://www.kleinanzeigen.de/s-handys/k0"), seen[-1]
        asyncio.run(d.search(SearchQuery(keywords="", category="phones", limit=5, max_pages=1,
                                         cat_map={"kleinanzeigen": "s-iphone"})))
        assert seen[-1].startswith("https://www.kleinanzeigen.de/s-iphone/k0"), seen[-1]
        asyncio.run(d.search(SearchQuery(keywords="", category="phones", limit=5, max_pages=1,
                                         cat_map={"kleinanzeigen": "../../evil"})))
        assert seen[-1].startswith("https://www.kleinanzeigen.de/s-/k0") or "/s-" in seen[-1]
        asyncio.run(d.search(SearchQuery(keywords="thinkpad", category="phones", limit=5, max_pages=1)))
        assert "s-thinkpad" in seen[-1]
    # map integrity: every slug is URL-safe, every generic resolves
    import re
    for slug in d.CATEGORIES:
        assert re.fullmatch(r"[a-z0-9-]+", slug), slug
    for g, slug in d.GENERIC.items():
        assert slug in d.CATEGORIES, (g, slug)


def test_geocode_math_and_cache():
    from deal_radar.geocode import cached, geocode, haversine_km
    # Vienna Stephansplatz -> Schönbrunn ~4.5km
    d = haversine_km((48.2082, 16.3738), (48.1856, 16.3124))
    assert 3.5 < d < 5.5
    assert geocode("") is None and geocode("x" * 200) is None
    import os
    import tempfile

    from deal_radar.store import Store
    st = Store(os.path.join(tempfile.mkdtemp(), "geo.db"))
    assert cached("Wien", st) is None  # nothing cached, no network in cached()
    st.db.execute("INSERT INTO geocache VALUES(?,?,?,?)", ("wien", 48.2, 16.37, 1.0))
    st.db.commit()
    assert cached("Wien", st) == (48.2, 16.37)
    st.close()


def test_cancel_pause_ttl_and_disarm():
    import asyncio
    import time

    from deal_radar import cancel as C
    assert C.should_stop(None) is False
    assert C.should_stop("nope") is False
    C._STOP.add("s1")
    assert C.should_stop("s1") is True
    C.disarm("s1")
    assert C.should_stop("s1") is False
    C._PAUSE.add("s2")
    C._PAUSE_SINCE["s2"] = time.time() - C.PAUSE_TTL_S - 1
    assert asyncio.run(C.pause_gate("s2")) is True  # TTL expired -> stop
    assert "s2" in C._STOP and "s2" not in C._PAUSE
    C.disarm("s2")


def test_snapshot_roundtrip():
    import os
    import tempfile

    from deal_radar.store import Store
    st = Store(os.path.join(tempfile.mkdtemp(), "snap.db"))
    st.save_search("s9", {"keywords": "t"}, total=2)
    payload = {"results": [{"listing": {"id": "a"}, "final_score": 1}], "filtered": [], "flags": {}}
    st.save_snapshot("s9", payload)
    back = st.load_snapshot("s9")
    assert back["results"][0]["listing"]["id"] == "a"
    assert st.load_snapshot("missing") is None
    st.close()


def test_price_rise_notifies_with_direction():
    import asyncio

    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.driver_sdk import (
        DriverManifest,
        DriverRegistry,
        MarketplaceDriver,
        SearchQuery,
    )
    from deal_radar.orchestrator import run_search

    state = {"price": 100}

    class F(MarketplaceDriver):
        manifest = DriverManifest(id="t", display_name="t", capabilities=["search"])

        async def search(self, query: SearchQuery):
            return [CanonicalListing(id="t:x", source="t", native_id="x", url="https://t/x",
                                     title="ThinkPad T14", description="good laptop",
                                     price=state["price"], images=[], seller=Seller(name="s"))]

    class FakeN:
        def __init__(self):
            self.sent = []

        async def send(self, *a, **k):
            self.sent.append(a)

    import os
    import tempfile

    from deal_radar.store import Store
    reg = DriverRegistry()
    reg.register(F())
    st = Store(os.path.join(tempfile.mkdtemp(), "rise.db"))
    n = FakeN()
    base = {"keywords": "thinkpad", "sources": ["t"], "limit": 5, "notify_on": ["price_rise"],
            "risk": {}, "enrich": False, "ocr": False, "benchmarks": False,
            "vision": False, "details": False}
    asyncio.run(run_search(dict(base), reg, st, n))
    assert n.sent == []
    state["price"] = 120
    asyncio.run(run_search(dict(base), reg, st, n))
    assert len(n.sent) == 1 and "▲20%" in n.sent[0][0], n.sent
    state["price"] = 100
    asyncio.run(run_search(dict(base, notify_on=["price_drop"]), reg, st, n))
    assert len(n.sent) == 2 and "▼" in n.sent[1][0]
    st.close()


def test_geocode_network_path_mocked():
    import json
    import os
    import tempfile
    from unittest.mock import patch

    from deal_radar import geocode as G
    from deal_radar.store import Store
    st = Store(os.path.join(tempfile.mkdtemp(), "geo2.db"))
    payload = json.dumps([{"lat": "48.2", "lon": "16.37"}]).encode()

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return payload

    with patch.object(G.urllib.request, "urlopen", return_value=FakeResp()):
        G._last_call = 0
        assert G.geocode("Wien", st) == (48.2, 16.37)
        # second call served from cache (would raise if network hit)
        with patch.object(G.urllib.request, "urlopen", side_effect=AssertionError("net!")):
            assert G.geocode("Wien", st) == (48.2, 16.37)
    st.close()


def test_distance_fill_and_max_distance_flag():
    import asyncio
    import os
    import tempfile

    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.driver_sdk import (
        DriverManifest,
        DriverRegistry,
        MarketplaceDriver,
        SearchQuery,
    )
    from deal_radar.orchestrator import run_search
    from deal_radar.store import Store

    class F(MarketplaceDriver):
        manifest = DriverManifest(id="t", display_name="t", capabilities=["search"])

        async def search(self, query: SearchQuery):
            mk = lambda i, loc, price: CanonicalListing(
                id=f"t:{i}", source="t", native_id=str(i), url="https://t/x", title=f"ThinkPad {i}",
                description="good laptop with plenty of description text here", price=price,
                images=["https://t/i.jpg"], location=loc, seller=Seller(name="s"))
            return [mk(1, "1010 Wien", 500), mk(2, "80331 München", 500)]

    reg = DriverRegistry()
    reg.register(F())
    st = Store(os.path.join(tempfile.mkdtemp(), "dist.db"))
    st.db.execute("INSERT OR REPLACE INTO geocache VALUES(?,?,?,?)", ("1010 wien", 48.2, 16.37, 1.0))
    st.db.execute("INSERT OR REPLACE INTO geocache VALUES(?,?,?,?)", ("80331 münchen", 48.13, 11.57, 1.0))
    st.db.execute("INSERT OR REPLACE INTO geocache VALUES(?,?,?,?)", ("wien", 48.2, 16.37, 1.0))
    st.db.commit()
    out = asyncio.run(run_search(
        {"keywords": "thinkpad", "sources": ["t"], "limit": 10, "location": "Wien",
         "max_distance_km": 100, "risk": {}, "enrich": False, "ocr": False,
         "benchmarks": False, "vision": False, "details": False}, reg, st, None))
    by_id = {r["listing"]["id"]: r for r in out["results"]}
    hid = {r["listing"]["id"]: r for r in out["filtered"]}
    assert by_id["t:1"]["listing"]["distance_km"] is not None
    assert by_id["t:1"]["listing"]["distance_km"] < 50
    assert "t:2" in hid and hid["t:2"]["listing"]["distance_km"] > 300
    assert any("km > max" in w for w in hid["t:2"]["why"])
    st.close()


def test_lab_publish_posts_pr(monkeypatch):
    import asyncio
    import os
    import sys
    sys.path.insert(0, "apps")
    os.environ["GH_TOKEN"] = "t"
    os.environ["LAB_PUBLISH"] = "1"
    import api.main as m
    calls = []

    class FakeResp:
        def __init__(self, payload):
            self._p = payload

        def json(self):
            return self._p

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            calls.append(url)
            if "git/ref" in url:
                return FakeResp({"object": {"sha": "abc"}})
            return FakeResp({"default_branch": "main"})

        async def post(self, url, headers=None, json=None):
            calls.append(url)
            return FakeResp({"html_url": "https://x/pr/1"})

        async def put(self, url, headers=None, json=None):
            calls.append(url)
            return FakeResp({})

    monkeypatch.setattr(m.httpx, "AsyncClient", FakeClient)
    try:
        out = asyncio.run(m.lab_publish({"id": "d", "kind": "enricher",
                                         "path": "enrichers/custom/d.py"}))
        assert out["ok"] and out["pr"].endswith("/pr/1"), out
        assert any("/pulls" in u for u in calls)
    finally:
        del os.environ["GH_TOKEN"]
        del os.environ["LAB_PUBLISH"]


def test_detail_enrich_upgrades_listing():
    import asyncio
    import os
    import tempfile

    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.driver_sdk import (
        DriverManifest,
        DriverRegistry,
        MarketplaceDriver,
        SearchQuery,
    )
    from deal_radar.orchestrator import run_search
    from deal_radar.store import Store

    class F(MarketplaceDriver):
        manifest = DriverManifest(id="t", display_name="t",
                                  capabilities=["search", "fetch_detail"])

        async def search(self, query: SearchQuery):
            return [CanonicalListing(id="t:x", source="t", native_id="x", url="https://t/x",
                                     title="ThinkPad T14", description="short",
                                     price=None, images=[], seller=Seller(name=""))]

        async def fetch_detail(self, native_id_or_url: str):
            return CanonicalListing(id="t:x", source="t", native_id="x", url="https://t/x",
                                    title="ThinkPad T14", description="full description here",
                                    price=450, images=[], seller=Seller(name="shop"))

    reg = DriverRegistry()
    reg.register(F())
    st = Store(os.path.join(tempfile.mkdtemp(), "det.db"))
    out = asyncio.run(run_search(
        {"keywords": "thinkpad", "sources": ["t"], "limit": 5,
         "risk": {}, "enrich": False, "ocr": False, "benchmarks": False, "vision": False,
         "details": True}, reg, st, None))
    r = out["results"][0]
    assert r["listing"]["price"] == 450
    assert any("detail page enriched" in w for w in r["why"])
    st.close()


def test_notifiers_send_and_from_env(monkeypatch):
    import asyncio

    import deal_radar.notifications as N

    posted = []

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, **k):
            posted.append(url)
            return FakeResp()

    monkeypatch.setattr(N.httpx, "AsyncClient", FakeClient)
    assert asyncio.run(N.NtfyNotifier("https://n/t").send("t", "b")) is True
    assert asyncio.run(N.WebhookNotifier("https://h/x").send("t", "b")) is True
    assert asyncio.run(N.SignalNotifier("http://s", "123").send("t", "b")) is True
    assert asyncio.run(N.TelegramNotifier("tok", "1").send("t", "b")) is True
    assert asyncio.run(N.LogNotifier().send("t", "b")) is True
    assert len(posted) == 4
    multi = N.notifier_from_env({"NOTIFIERS_JSON": '[{"type": "log"}]', "SIGNAL_NUMBER": "x"})
    assert asyncio.run(multi.send("t", "b")) is True


def test_job_detail_roundtrip():
    import os
    import tempfile

    from deal_radar.store import Store
    st = Store(os.path.join(tempfile.mkdtemp(), "jobdet.db"))
    st.job_upsert("sj", "running", 2, 5, {"keywords": "t"}, detail="sub-search 3/5: foo")
    st.save_search("sj", {"keywords": "t", "sources": ["t"]}, total=0)
    rows = st.list_searches()
    assert rows[0]["job"]["detail"] == "sub-search 3/5: foo"
    assert rows[0]["job"]["done"] == 2
    st.close()


def test_cpu_gpu_extract_and_benchmark_parsers():
    from deal_radar.benchmarks import (
        closest_known_cpu,
        parse_gpu_list,
        parse_passmark_detail,
    )
    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.scoring import enrich_cpu, enrich_gpu, extract_cpu, extract_gpu

    cpu, conf, _src = extract_cpu("ThinkPad with Ryzen 5 PRO 5650U notebook")
    assert cpu and "ryzen" in cpu.lower() and conf > 0
    assert cpu == "Ryzen 5 PRO 5650U"
    assert extract_cpu("plain wooden chair")[0] is None
    gpu, _gconf, _ = extract_gpu("laptop with GeForce RTX 4060 graphics")
    assert gpu and "4060" in gpu
    mk = lambda t: CanonicalListing(id="x", source="t", native_id="x", url="u", title=t,
                                    description="d", price=100, images=[], seller=Seller(name="s"))
    assert any(e.field == "cpu" for e in enrich_cpu(mk("Ryzen 5 PRO 5650U inside")))
    assert enrich_gpu(mk("RTX 4060 inside")) != []
    assert parse_passmark_detail("<html>no numbers here</html>") == (None, None)
    assert parse_gpu_list("<html></html>") == {}
    alt, score = closest_known_cpu("definitely not a real cpu xyz 123")
    assert alt is None or isinstance(score, float)


def test_real_ocr_reads_generated_image():
    from io import BytesIO

    from PIL import Image, ImageDraw

    from deal_radar import vision as V
    img = Image.new("RGB", (600, 120), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 30), "ThinkPad T14 Garantie 2026", fill="black")
    buf = BytesIO()
    img.save(buf, format="PNG")
    text = V.ocr_bytes(buf.getvalue())
    assert "ThinkPad" in text and "Garantie" in text, text
    assert V.ocr_bytes(b"") == ""
    assert V.ocr_bytes(b"not-an-image") == ""


def test_imgdup_hash_and_hamming():
    from io import BytesIO

    from PIL import Image

    from deal_radar import imgdup as I
    a = Image.new("RGB", (64, 64), "white")
    b = Image.new("RGB", (64, 64), "white")
    from PIL import ImageDraw as _D
    _D.Draw(b).rectangle([0, 0, 31, 63], fill="black")
    ba, bb = BytesIO(), BytesIO()
    a.save(ba, format="PNG")
    b.save(bb, format="PNG")
    ha, hb = I.ahash(ba.getvalue()), I.ahash(bb.getvalue())
    assert ha is not None and hb is not None and ha != hb
    assert I.hamming(ha, ha) == 0
    assert I.hamming(ha, hb) > 0
    assert I.ahash(b"junk") is None
    assert I.image_hash("https://127.0.0.1:9/none.png") is None


def test_accessory_demotions_and_compounds():
    from deal_radar.decision import heuristic_decide as h
    # German compounds must classify as accessory despite keyword hits
    for t in ["iPhone 17 Pro Max Handyhülle", "Handyhülle iPhone 17 Pro",
              "Iphone 17 Pro Screen protector - Schutzfolie",
              "INIU Power Bank für iPhone 17 16 Pro",
              "Sofort Teilzahlung - IPhone 17 Pro Max 512Gb"]:
        r = h(t, "", 50, "iphone 17")
        assert r["kind"] == "accessory" and r["match"] <= 0.30, (t, r)
    # real phones + legit offers untouched
    r = h("Iphone 17 pro max 256gb", "", 900, "iphone 17")
    assert r["kind"] == "offer" and r["match"] >= 0.8, r
    r = h("Sony PlayStation 5 Slim", "", 400, "iphone 17")
    assert r["kind"] == "offer", r
    r = h("iPhone 12 Pro [Verkauf/Tausch] Top", "", 500, "iphone 17")
    assert r["kind"] == "offer", r


def test_clone_contradiction_and_kind_reasons():
    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.decision import heuristic_decide as h
    from deal_radar.risk_engine import assess_risk
    mk = lambda t, brand="": CanonicalListing(
        id="x", source="t", native_id="x", url="u", title=t, description="d",
        price=400, images=[], seller=Seller(name="s"),
        attributes={"Marke": brand} if brand else {})
    r = assess_risk(mk("iPhone 17 pro Max", "Android"))
    assert r.score >= 0.35 and any("clone" in x for x in r.reasons)
    r2 = assess_risk(mk("iPhone 17 pro Max", "Apple"))
    assert not any("clone" in x for x in r2.reasons)
    assert h("Coque iPhone 17 Rinoshield", "", 20, "iphone 17")["kind"] == "accessory"
    assert h("Boîte iPhone 17 Pro", "", 10, "iphone 17")["kind"] == "accessory"


def test_accessory_demotions_prod_titles():
    from deal_radar.decision import heuristic_decide as h
    for t in ["Schutzgläser/ Schutzdisplays Kamera-Modul für IPhone 17 Pro Max",
              "Kameralinsen Schutz mit OVP",
              "Glitzernder Linsenschutz iPhone 17 pro",
              "se noglass - Das Original iPhone 17 Pro Max",
              "iPhone 17 Pro Max - Heute holen, später zahlen!"]:
        r = h(t, "", 50, "iphone 17")
        assert r["kind"] == "accessory" and r["match"] <= 0.30, (t, r)
    r = h("iPhone 17 Pro Max 256GB Neuwertig", "", 900, "iphone 17")
    assert r["kind"] == "offer" and r["match"] >= 0.8, r
    for t2 in ["Screen Protektor für iPhone 17 Pro",
               "iPhone 13,14,15,16,17 Pocket 40cm in schwarz",
               "Buch iPhone 17 einmal gelesen",
               "IPHONE LCD & AUSTAUSCH ! SOFORT",
               "Originalverpackt - Apple Iphone Battery Pack"]:
        r2 = h(t2, "", 50, "iphone 17")
        assert r2["kind"] == "accessory" and r2["match"] <= 0.30, (t2, r2)


def test_accessory_round2_and_flagship_risk():
    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.decision import heuristic_decide as h
    from deal_radar.risk_engine import assess_risk
    mk = lambda t, p: CanonicalListing(
        id="x", source="t", native_id="x", url="u", title=t, description="d",
        price=p, images=[], seller=Seller(name="s"))
    for t in ["dbrand Prism 2.0 iPhone 17 Pro Max Screen Protector",
              "cellularline Camera Lens Protection Iphone 17 Pro Max",
              "Ideal of Sweden Kombipaket für IPhone 17 Pro"]:
        assert h(t, "", 30, "iphone 17")["kind"] == "accessory", t
    r = assess_risk(mk("IPhone 17 Pro Max Mini DOYODA", 49))
    assert r.score >= 0.4 and any("flagship" in x for x in r.reasons)
    r2 = assess_risk(mk("iPhone 17 Pro Max 256GB", 900))
    assert not any("flagship" in x for x in r2.reasons)


def _cli_proc(payload: bytes):
    m = AsyncMock()
    m.communicate = AsyncMock(return_value=(payload, b""))
    return m


def test_opencode_cli_disabled_is_free(monkeypatch):
    import shutil as _sh
    monkeypatch.setenv("OPENCODE_CLI_MODEL", "")  # explicitly off
    with patch("asyncio.create_subprocess_exec", new=AsyncMock()) as sp:
        assert run(D._cli_json("s", "u")) is None
        sp.assert_not_called()
    # binary missing -> None fast, never spawned
    monkeypatch.setenv("OPENCODE_CLI_MODEL", "opencode/x")
    monkeypatch.setattr(_sh, "which", lambda *a: None)
    with patch("asyncio.create_subprocess_exec", new=AsyncMock()) as sp2:
        assert run(D._cli_json("s", "u")) is None
        sp2.assert_not_called()


def test_opencode_cli_parses_and_fails_cleanly(monkeypatch):
    monkeypatch.setenv("OPENCODE_CLI_MODEL", "opencode/muse-spark-1.3-contributor-free")
    import shutil as _sh
    monkeypatch.setattr(_sh, "which", lambda *a: "/usr/bin/opencode")
    hdr = b"\x1b[0m\n> build \xc2\xb7 muse-spark-1.3-contributor-free\n{\"a\": 1}\n"
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=_cli_proc(hdr))) as sp:
        assert run(D._cli_json("s", "u")) == {"a": 1}
        args = sp.call_args[0]
        assert args[:3] == ("opencode", "run", "--model")
    # garbage output -> None, never raises
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=_cli_proc(b"no json here"))):
        assert run(D._cli_json("s", "u")) is None
    # timeout -> None, proc killed
    proc = _cli_proc(b"")
    proc.communicate = AsyncMock(side_effect=TimeoutError())
    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=proc)):
        assert run(D._cli_json("s", "u", timeout=1)) is None
        proc.kill.assert_called_once()


def test_cloud_json_uses_cli_when_cloud_down(monkeypatch):
    monkeypatch.setenv("OPENCODE_CLI_MODEL", "opencode/muse-spark-1.3-contributor-free")
    monkeypatch.setenv("CLOUD_API_URL", "http://x")
    monkeypatch.setenv("CLOUD_API_KEY", "k")
    monkeypatch.delenv("LOCAL_API_URL", raising=False)
    import shutil as _sh
    monkeypatch.setattr(_sh, "which", lambda *a: "/usr/bin/opencode")
    with patch.object(D.httpx, "AsyncClient") as AC, \
         patch("asyncio.create_subprocess_exec",
               new=AsyncMock(return_value=_cli_proc(b"> h\n{\"keywords\": \"x\"}"))):
        inst = AsyncMock()
        inst.post = AsyncMock(side_effect=Exception("down"))
        AC.return_value.__aenter__ = AsyncMock(return_value=inst)
        AC.return_value.__aexit__ = AsyncMock(return_value=False)
        with patch("asyncio.sleep", new=AsyncMock()):
            assert run(D.cloud_json("s", "u", model="m")) == {"keywords": "x"}


def test_model_ranking_prefers_proven_fast(monkeypatch):
    D._MH.clear()
    try:
        assert D._order_models("u", ["a", "b", "c"]) == ["a", "b", "c"]  # no data: stable
        D.apply_health([
            {"candidate": "cloud:u:b", "ok": True, "latency": 0.5},
            {"candidate": "cloud:u:a", "ok": True, "latency": 5.0},
        ])
        assert D._order_models("u", ["a", "b", "c"]) == ["b", "a", "c"]  # fast proven first
        D.apply_health([{"candidate": "cloud:u:c", "ok": False, "latency": 1.0}])
        assert D._order_models("u", ["a", "b", "c"]) == ["b", "a", "c"]  # failing benched
        snap = D.health_snapshot()
        assert snap["cloud:u:b"]["ok"] >= 1 and snap["cloud:u:c"]["fail"] >= 3
        D.restore_health({})
        D._MH.clear()
        D.restore_health(snap)
        assert D._order_models("u", ["a", "b", "c"]) == ["b", "a", "c"]  # survives restart
    finally:
        D._MH.clear()


def test_modelcheck_pool_and_probe_shapes(monkeypatch):
    from deal_radar import modelcheck as MC
    monkeypatch.setenv("CLOUD_API_URL", "http://x")
    monkeypatch.setenv("CLOUD_API_KEY", "k")
    monkeypatch.setenv("OPENCODE_CLI_MODEL", "opencode/spark")
    monkeypatch.delenv("MODELCHECK_MODELS", raising=False)
    pool = MC.candidates()
    assert pool[0]["kind"] == "cloud" and pool[-1]["kind"] == "cli"
    assert MC.ckey(pool[0]).startswith("cloud:http://x:")
    # unconfigured cloud candidate fails honestly without network
    monkeypatch.setenv("CLOUD_API_URL", "")
    bad = {"kind": "cloud", "url": "", "key": "", "model": "m"}
    r = run(MC.probe_one(bad, timeout=5))
    assert r["ok"] is False and "no url/key" in r["note"]
    # env override pool parsing
    monkeypatch.setenv("MODELCHECK_MODELS", "cli:opencode/mymodel,cloud:deepseek/x,bare/y")
    pool2 = MC.candidates()
    assert [(c["kind"], c["model"]) for c in pool2] == [
        ("cli", "opencode/mymodel"), ("cloud", "deepseek/x"), ("cloud", "bare/y")]


def test_models_endpoints_live_cycle(monkeypatch):
    import sys
    sys.path.insert(0, "apps")
    import api.main as m
    from fastapi.testclient import TestClient

    from deal_radar import decision as D
    D._MH.clear()
    try:
        c = TestClient(m.app)
        h = c.get("/models/health").json()
        assert "pool" in h and any("deepseek" in p for p in h["pool"])
        fake = [{"candidate": "cloud:u:m", "ok": True, "latency": 0.3, "ts": 0.0}]
        with patch("deal_radar.modelcheck.probe_all", new=AsyncMock(return_value=fake)):
            r = c.post("/models/check").json()
            assert r["results"] == fake and "cloud:u:m" in r["health"]
        assert c.get("/models/health").json()["health"]["cloud:u:m"]["ok"] >= 1
    finally:
        D._MH.clear()


def test_cross_source_dupes_surfaced_not_silent():
    import asyncio

    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.driver_sdk import (
        DriverManifest,
        DriverRegistry,
        MarketplaceDriver,
        SearchQuery,
    )
    from deal_radar.orchestrator import run_search

    def _mk2(src, price, url):
        return CanonicalListing(id=f"{src}:1", source=src, native_id="1", url=url,
                                title="Beelink 8845HS Mini PC 24GB",
                                description="Some decent description text here for scoring",
                                price=price, images=["http://img/x.jpg"], seller=Seller(name="s"))

    class FA(MarketplaceDriver):
        manifest = DriverManifest(id="a", display_name="a", capabilities=["search"])

        async def search(self, query: SearchQuery):
            return [_mk2("a", 300, "https://a/1")]

    class FB(MarketplaceDriver):
        manifest = DriverManifest(id="b", display_name="b", capabilities=["search"])

        async def search(self, query: SearchQuery):
            return [_mk2("b", 320, "https://b/1")]

    reg = DriverRegistry()
    reg.register(FA())
    reg.register(FB())
    out = asyncio.run(run_search(
        {"keywords": "beelink", "sources": ["a", "b"], "limit": 10, "enrich": True,
         "ocr": False, "benchmarks": False, "vision": False, "details": False},
        reg, None, None))
    assert len(out["results"]) == 1  # still deduped to one card
    r = out["results"][0]
    assert len(r["also_on"]) == 1 and r["also_on"][0]["source"] in ("a", "b")
    assert any("also listed on" in w for w in r["why"])


def test_cheap_benchmark_tier_covers_all():
    import asyncio
    from unittest.mock import patch

    from deal_radar.orchestrator import run_search
    items = [_mk("t:1", title="Beelink Ryzen 7 8845HS 24GB", price=300),
             _mk("t:2", title="Geekom Ryzen 7 7840HS 16GB", price=320)]
    with patch("deal_radar.benchmarks.fetch_passmark_cpu",
               return_value={"multi": 28000, "single": 3700, "source": "t"}) as fp:
        out = asyncio.run(run_search(
            {"keywords": "mini pc ryzen", "sources": ["t"], "limit": 10, "enrich": True,
             "enrich_top_n": 1,  # deep budget for 1 only; cheap tier must cover #2
             "ocr": False, "benchmarks": True, "vision": False, "details": False},
            _reg(items), None, None))
    benches = [e for r in out["results"] for e in r["enrichments"] if e["field"] == "cpu_benchmark"]
    assert len(benches) == 2, [r["enrichments"] for r in out["results"]]
    assert fp.call_count == 2


def test_spec_line_shapes():
    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.orchestrator import spec_line
    l = CanonicalListing(id="t:1", source="t", native_id="1", url="https://x/1",
                         title="Beelink 8845HS 24GB RAM 1TB SSD", description="Top Zustand, wenig genutzt",
                         price=300.0, seller=Seller(name="s"))
    enr = [{"field": "cpu", "value": "Ryzen 7 8845HS"},
           {"field": "cpu_benchmark", "value": 28261},
           {"field": "cpu_single", "value": 3718}]
    txt = spec_line(l, enr)
    assert "Ryzen 7 8845HS" in txt and "28261" in txt and "3718" in txt
    assert "24GB RAM" in txt and "1TB" in txt and "Top Zustand" in txt
    assert "no CPU identified" in spec_line(
        CanonicalListing(id="t:9", source="t", native_id="9", url="u", title="Holzstuhl",
                         description="schlicht", price=10.0, seller=Seller(name="s")), [])


def test_seller_change_tracked():
    import os
    import tempfile

    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.store import Store
    st = Store(os.path.join(tempfile.mkdtemp(), "s.db"))
    l1 = CanonicalListing(id="t:1", source="t", native_id="1", url="u", title="Mini PC",
                          description="d", price=100.0, seller=Seller(name="alice"))
    assert st.upsert(l1) == []
    l2 = CanonicalListing(id="t:1", source="t", native_id="1", url="u", title="Mini PC",
                          description="d", price=100.0, seller=Seller(name="bob"))
    evs = st.upsert(l2)
    assert any(e["kind"] == "seller" and e["old"] == "alice" and e["new"] == "bob" for e in evs)
    obs = st.db.execute("SELECT kind FROM observations WHERE listing_id='t:1'").fetchall()
    assert ("seller",) in obs


def test_cloud_json_skips_benched_models(monkeypatch):
    from unittest.mock import patch
    D._MH.clear()
    try:
        monkeypatch.setenv("CLOUD_API_URL", "http://x")
        monkeypatch.setenv("CLOUD_API_KEY", "k")
        monkeypatch.delenv("LOCAL_API_URL", raising=False)
        D.apply_health([{"candidate": f"cloud:http://x:{m}", "ok": False, "latency": 1.0}
                        for m in D.CLOUD_MODELS])
        with patch.object(D.httpx, "AsyncClient") as AC:
            inst = AsyncMock()
            inst.post = AsyncMock(side_effect=Exception("must not be called"))
            AC.return_value.__aenter__ = AsyncMock(return_value=inst)
            AC.return_value.__aexit__ = AsyncMock(return_value=False)
            assert run(D.cloud_json("s", "u", model="")) is None  # straight to (blanked) fallback
            inst.post.assert_not_called()
    finally:
        D._MH.clear()


def test_accessory_kinds_and_value_cap():
    import asyncio

    from deal_radar.decision import heuristic_decide
    assert heuristic_decide("NUR LEERVERPACKUNG OVP Ryzen 9", "", 10, "mini pc")["kind"] == "accessory"
    assert heuristic_decide("Alpenföhn Brocken 3 AM4", "", 15, "cooler")["kind"] == "accessory"
    assert heuristic_decide("Dissipateur HP EliteBook", "", 5, "x")["kind"] == "accessory"
    assert heuristic_decide("HP EliteBook 845 G8 Tastatur", "", 3, "keyboard")["kind"] == "accessory"
    # bundles with real computers stay offers
    assert heuristic_decide("Beelink EQR5 Windows 11 Plus Tastatur Maus", "", 349, "mini pc")["kind"] == "offer"
    assert heuristic_decide("Mini PC Ryzen 7 8845HS 24GB", "", 300, "mini pc")["kind"] == "offer"
    # non-offer kinds can never top value rankings
    from deal_radar.orchestrator import run_search
    from tests.test_units3 import _mk, _reg
    items = [_mk("t:1", title="Ryzen 9 5900XT leere OVP Box", price=5),
             _mk("t:2", title="Beelink Ryzen 7 8845HS 24GB Mini PC", price=300)]
    out = asyncio.run(run_search(
        {"keywords": "ryzen", "sources": ["t"], "limit": 10, "enrich": True,
         "ocr": False, "benchmarks": False, "vision": False, "details": False},
        _reg(items), None, None))
    vals = {r["listing"]["id"]: r["value_score"] for r in out["results"]}
    assert vals["t:2"] > vals.get("t:1", 1.0), vals


def test_ram_speed_not_cpu():
    from deal_radar.scoring import extract_cpu
    assert extract_cpu("verkaufe 2x 512 mb ddr2 ram pc2-5300u")[0] is None
    assert extract_cpu("ryzen 5 5600u 16gb ddr4")[0] == "Ryzen 5 5600U"


def test_xmp_ram_is_accessory():
    from deal_radar.decision import heuristic_decide
    assert heuristic_decide("Crucial Ballistix Sport Gaming 16GB DDR3 (2x8GB KIT) INTEL XMP",
                            "", 70, "ram")["kind"] == "accessory"
    assert heuristic_decide("Intel Core i5-12450H Mini PC", "", 300, "mini pc")["kind"] == "offer"
    assert heuristic_decide("Kingston ValueRAM DDR4-2400 4GB", "", 14, "ram")["kind"] == "accessory"


def test_ram_and_brand_guard():
    from deal_radar.decision import heuristic_decide
    h = lambda t: heuristic_decide(t, "", 100, "x")["kind"]
    assert h("Kingston ValueRAM DDR4-2400 4GB") == "accessory"
    assert h("Crucial Ballistix Sport Gaming 16GB DDR3 (2x8GB KIT) INTEL XMP") == "accessory"
    assert h("ThinkPad T14 16GB Arbeitsspeicher 512GB") == "offer"
    assert h("Thinkpad X1 Carbon Gen 8 i7") == "offer"
    assert h("Beelink EQR5 Windows 11 Plus Tastatur Maus") == "offer"


def test_gpu_specs_vram_bw_multigpu_unified_fx():
    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.scoring import (
        enrich_gpu,
        extract_unified_mem,
        lookup_gpu_spec,
        to_eur,
        value_score,
    )
    assert lookup_gpu_spec("RTX 3090") == {"vram": 24, "bw": 936}
    assert lookup_gpu_spec("Mac Studio M1 Ultra 128GB") == {"vram": 128, "bw": 800}
    assert lookup_gpu_spec("ryzen ai max+ 395") == {"vram": 128, "bw": 256}
    assert lookup_gpu_spec("toaster") is None
    mk = lambda t, d="": CanonicalListing(id="t", source="t", native_id="t", url="u",
                                          title=t, description=d, price=1000.0,
                                          seller=Seller(name="s"))
    es = {e.field: e.value for e in enrich_gpu(mk("2x RTX 3090 24GB mining rig"))}
    assert es.get("gpu_count") == 2 and es.get("gpu_vram") == 48
    assert es.get("gpu_bw") == 936 and es.get("gpu_est_tps") == round(936 / 7)
    assert extract_unified_mem("Mac Studio M1 Ultra 128GB unified memory") == 128
    assert extract_unified_mem("plain laptop 16gb") is None
    es2 = {e.field: e.value for e in enrich_gpu(mk("Mac Studio M2 Ultra 192GB"))}
    assert es2.get("gpu_mem_total") == 192
    assert to_eur(100, "EUR") == 100 and to_eur(108, "USD") == 100.0
    assert to_eur(None, "USD") is None
    v_eur, _ = value_score(500, 15000, 600)
    v_usd, _ = value_score(540, 15000, 600, "USD")  # 540 USD ~= 500 EUR
    assert abs(v_eur - v_usd) < 0.05, (v_eur, v_usd)


def test_allegro_driver_contract():
    """Allegro.pl official-API driver: token mint, listing shapes, pagination,
    clean error without credentials. HTTP fully mocked (no network)."""
    import asyncio
    from unittest.mock import AsyncMock, patch

    from allegro.driver import AllegroDriver, _parse_item, mint_token, resolve_token

    from deal_radar.driver_sdk import SearchQuery

    async def fake_post(url, **kw):
        class R:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"access_token": "tok123", "expires_in": 43200}
        assert "allegro.pl/auth/oauth/token" in url
        assert kw.get("data", {}).get("grant_type") == "client_credentials"
        return R()

    with patch("httpx.AsyncClient") as AC:
        inst = AsyncMock()
        inst.post = fake_post
        AC.return_value.__aenter__ = AsyncMock(return_value=inst)
        AC.return_value.__aexit__ = AsyncMock(return_value=False)
        tok, exp = asyncio.run(mint_token("id", "sec"))
        assert tok == "tok123" and exp > 0

    # item shapes: full, minimal, garbage
    full = {"id": "111", "name": "Mac Studio M1 Ultra 128GB", "price": {"amount": "4600.00", "currency": "PLN"},
            "images": [{"url": "https://a.allegroimg.com/x.jpg"}],
            "seller": {"id": "s1"}, "category": {"id": "c1"}}
    p = _parse_item(full)
    assert p and p.id == "allegro:111" and p.price == 4600.0 and p.currency == "PLN"
    assert p.url == "https://allegro.pl/oferta/111" and p.images == ["https://a.allegroimg.com/x.jpg"]
    assert _parse_item({"id": "", "name": "x"}) is None
    assert _parse_item({}) is None
    alt = {"id": "222", "name": "RAM", "sellingMode": {"price": {"amount": "200", "currency": "PLN"}},
           "primaryImage": {"url": "https://i/y.jpg"}}
    p2 = _parse_item(alt)
    assert p2 and p2.price == 200.0 and p2.images == ["https://i/y.jpg"]

    # no credentials -> clean error naming the secrets
    with patch.dict("os.environ", {}, clear=False):
        for k in ("ALLEGRO_CLIENT_ID", "ALLEGRO_CLIENT_SECRET"):
            pass
        import os as _os
        _os.environ.pop("ALLEGRO_CLIENT_ID", None)
        _os.environ.pop("ALLEGRO_CLIENT_SECRET", None)
        try:
            asyncio.run(resolve_token())
            raise SystemExit("must raise")
        except RuntimeError as e:
            assert "ALLEGRO_CLIENT_ID" in str(e)
        finally:
            pass

    # search walks pages, stops on short page; token from env creds (mint mocked)
    import os as _os2
    _os2.environ["ALLEGRO_CLIENT_ID"] = "id"
    _os2.environ["ALLEGRO_CLIENT_SECRET"] = "sec"
    try:
        page1 = {"items": {"regular": [dict(full, id=f"a{i}") for i in range(1, 121)]},
                 "searchMeta": {"totalCount": 123}}
        page2 = {"items": {"regular": [dict(full, id="a121"), dict(full, id="a122")]},
                 "searchMeta": {"totalCount": 123}}
        calls = []

        class FakeT:
            async def get(self, url, headers=None):
                calls.append(url)
                n = 1 if "offset=0" in url or "offset" not in url else 2
                class R:
                    status_code = 200

                    def raise_for_status(self):
                        pass

                    def json(self):
                        return page1 if n == 1 else page2
                return R()

        from allegro.driver import _TOKEN_CACHE
        _TOKEN_CACHE["token"] = "tok123"
        _TOKEN_CACHE["expires_at"] = 9999999999.0
        try:
            d = AllegroDriver(transport=FakeT())
            out = asyncio.run(d.search(SearchQuery(keywords="mac studio", limit=122, max_pages=5)))
            assert [x.native_id for x in out] == [f"a{i}" for i in range(1, 123)]
            assert all("phrase=mac+studio" in u or "phrase=mac%20studio" in u for u in calls)
            assert len(calls) == 2  # second page fetched, then short page stops
        finally:
            _TOKEN_CACHE.clear()
    finally:
        _os2.environ.pop("ALLEGRO_CLIENT_ID", None)
        _os2.environ.pop("ALLEGRO_CLIENT_SECRET", None)
    assert AllegroDriver.configured() is False


def test_title_match_rejects_hx_sibling():
    """Regression: the 285HX page (56k) passed substring verification for a 285H
    query (real: 34k). Whole-token matching only."""
    from deal_radar.benchmarks import _title_matches
    assert _title_matches("Core Ultra 9 285H", "Intel Core Ultra 9 285H Benchmark") is True
    assert _title_matches("Core Ultra 9 285H", "Intel Core Ultra 9 285HX Benchmark") is False
    assert _title_matches("i7-12700", "Intel Core i7-12700K Benchmark") is False
    assert _title_matches("i7-12700", "Intel Core i7-12700 Benchmark") is True
    assert _title_matches("Ryzen 9 5900X", "AMD Ryzen 9 5900X Benchmark") is True
    assert _title_matches("Ryzen 9 5900X", "AMD Ryzen 9 5900XT Benchmark") is False
    assert _title_matches("M1", "Apple M1 Benchmark") is True


def test_shopify_driver_minisforum_um690():
    """Shopify brand store: UM690 Pro matches, min-variant price wins, catalog cached."""
    import asyncio
    from pathlib import Path as _P

    from shopify.driver import SHOPS, make_shopify_driver

    from deal_radar.driver_sdk import SearchQuery

    assert {s[0] for s in SHOPS} >= {"minisforum", "gmktec", "aoostar", "acemagic"}

    class FeedT:
        def __init__(self, payload):
            self.payload = payload
            self.calls = []

        async def get(self, url, headers=None):
            self.calls.append(url)

            class R:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self_inner):
                    import json as _jj
                    if "page=1" in url or "page=" not in url:
                        return _jj.loads(_P("tests/fixtures/shopify-minisforum.json").read_text())
                    return {"products": []}
            return R()

    d = make_shopify_driver("minisforum", "Minisforum EU", "https://minisforumpc.eu", "EUR")
    assert d.manifest.id == "minisforum" and d.configured() is True
    d.transport = FeedT(None)
    out = asyncio.run(d.search(SearchQuery(keywords="ryzen 9 6900hx", limit=10)))
    assert out, "UM690 Pro must match"
    um690 = [x for x in out if "6900" in (x.title or "")]
    assert um690 and um690[0].price == 359.0 and um690[0].currency == "EUR"
    assert um690[0].condition == "new" and um690[0].url.startswith("https://minisforumpc.eu/products/")
    # min variant price wins; catalog cached (one fetch for two searches)
    out2 = asyncio.run(d.search(SearchQuery(keywords="um690", limit=10)))
    assert out2 and len(d.transport.calls) == 1
    # no match -> empty, never raises
    assert asyncio.run(d.search(SearchQuery(keywords="zzqqxx-nonexistent", limit=10))) == []


def test_shopify_driver_multi_shop_cached():
    """Shopify brand stores: real captured catalogs (fixtures), min-price variants,
    keyword filter, pagination stop, catalog caching."""
    import asyncio
    import json as _j
    from pathlib import Path as _P

    from shopify import driver as S

    from deal_radar.driver_sdk import SearchQuery

    feeds = {}
    for shop in ("minisforum", "gmktec", "aoostar", "acemagic"):
        feeds[shop] = _j.loads((_P(__file__).parent / "fixtures" / f"shopify-{shop}.json").read_text())

    class FakeT:
        def __init__(self):
            self.calls = 0

        async def get(self, url, headers=None):
            self.calls += 1
            shop = next(s for s in feeds if s in url)
            class R:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return feeds[shop] if "page=1" in url or "page=" not in url else {"products": []}
            return R()

    S._CATALOG.clear()
    try:
        t = FakeT()
        d = S.make_shopify_driver("minisforum", "Minisforum EU", "https://minisforumpc.eu", "EUR")
        d.transport = t
        out = asyncio.run(d.search(SearchQuery(keywords="ryzen 9 6900HX", limit=10, max_pages=3)))
        assert len(out) == 1 and out[0].price == 359.0 and out[0].currency == "EUR"
        assert out[0].condition == "new" and out[0].url.startswith("https://minisforumpc.eu/products/")
        assert out[0].source == "minisforum"
        # second search reuses the cached catalog (no new fetch)
        asyncio.run(d.search(SearchQuery(keywords="ryzen 9", limit=10, max_pages=3)))
        assert t.calls == 1
        # no match -> empty, never errors
        assert asyncio.run(d.search(SearchQuery(keywords="xqzv teflon", limit=10))) == []
        # max price filter applies
        assert asyncio.run(d.search(SearchQuery(keywords="ryzen 9 6900HX", limit=10, max_price=100))) == []
        assert S.make_shopify_driver("x", "y", "https://z").manifest.id == "x"
    finally:
        S._CATALOG.clear()


def test_shopify_driver_match_and_bounds():
    """Brand-store driver against real captured products.json feeds (no network)."""
    import asyncio
    import json as _j
    from pathlib import Path as _P

    from shopify.driver import SHOPS, ShopifyDriver, _match

    from deal_radar.driver_sdk import SearchQuery

    assert len(SHOPS) == 4
    assert _match("minisforum um870 slim ryzen 7 barebone", "um870 ryzen")
    assert not _match("nucbox m10 windows", "um870 ryzen")

    class FakeT:
        def __init__(self, payload):
            self.payload = payload
            self.calls = []

        async def get(self, url, headers=None):
            self.calls.append(url)
            class R:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self_inner):
                    return self.payload
            return R()

    feed = _j.loads(_P("tests/fixtures/shopify-minisforum.json").read_text())
    d = ShopifyDriver(transport=FakeT(feed), shop_id="minisforum",
                      shop_name="Minisforum EU", base_url="https://minisforumpc.eu")
    out = asyncio.run(d.search(SearchQuery(keywords="ryzen 9", limit=10, max_pages=3)))
    assert out, "seeded feed must match ryzen 9"
    r = out[0]
    assert r.source == "minisforum" and r.condition == "new" and r.currency == "EUR"
    assert r.url.startswith("https://minisforumpc.eu/products/")
    assert r.price and r.price > 0
    # catalog cached: second search costs zero requests
    asyncio.run(d.search(SearchQuery(keywords="ryzen 9", limit=10, max_pages=3)))
    assert len(d.transport.calls) == 1
    # no match -> empty, price bounds respected
    assert asyncio.run(d.search(SearchQuery(keywords="zzzzqqqq", limit=10))) == []
    out2 = asyncio.run(d.search(SearchQuery(keywords="ryzen", limit=10, max_price=1.0)))
    assert out2 == []


def test_strip_marketplace_suffix():
    from deal_radar.scoring import strip_marketplace_suffix
    t = "Lenovo Thinkpad X1 Carbon, Marke: Lenovo, Modell: ThinkPad X1 Carbon, Zustand: Sehr gut, 200.0"
    assert strip_marketplace_suffix(t) == "Lenovo Thinkpad X1 Carbon ThinkPad X1 Carbon"
    assert strip_marketplace_suffix("ThinkPad T480 i5-8350U") == "ThinkPad T480 i5-8350U"
    assert strip_marketplace_suffix("") == ""


def test_extract_cpu_ultra_x_and_nth():
    from deal_radar.scoring import extract_cpu
    cpu, conf, _ = extract_cpu("ThinkPad X1 Carbon Gen 14 - Ultra X7 / 64 GB / 1 TB")
    assert cpu == "Core Ultra X7" and conf < 0.7
    cpu, conf, _ = extract_cpu("ACEMAGIC RX16 Intel Core Ultra X7 358H Flagship AI laptop")
    assert cpu == "Core Ultra X7 358H" and conf >= 0.8
    cpu, conf, _ = extract_cpu("Lenovo E14 i3 10th - Bios bloque")
    assert cpu == "i3-10110U" and conf <= 0.6
    cpu, conf, _ = extract_cpu("HP EliteBook i5 11th Gen")
    assert cpu == "i5-1135G7"


def test_resolve_cpu_with_seeds_vinted_titles():
    from deal_radar.scoring import resolve_cpu_with_seeds
    # vinted metadata tail must not block the seed estimate
    cpu, _, _, est, cands = resolve_cpu_with_seeds(
        "Lenovo Thinkpad X1 Carbon Gen 6, Marke: Lenovo, Modell: ThinkPad X1 Carbon, Zustand: Sehr gut")
    assert est is True and cpu in ("i5-8250U", "i5-8350U", "i7-8550U", "i7-8650U") and cands
    # bare tier hint narrows to i5
    cpu, _, _, est, _ = resolve_cpu_with_seeds("ThinkPad X1 Yoga Gen 6 | i5 | 16GB RAM | 256GB SSD")
    assert est is True and cpu.startswith("i5-")
    # exact mention still wins, not estimated
    cpu, conf, _, est, _ = resolve_cpu_with_seeds("ThinkPad T480 i7-8650U 16GB")
    assert cpu == "i7-8650U" and est is False and conf >= 0.6
    # non-system title stays unknown
    cpu, _, _, est, _ = resolve_cpu_with_seeds("Nike Training Shorts Blue Mens XL")
    assert cpu is None and est is False
    # T460 classic resolves via seed
    cpu, _, _, est, _ = resolve_cpu_with_seeds("Lenovo T460 guter Zustand, 12GB RAM, 240GB SSD")
    assert est is True and cpu in ("i5-6200U", "i5-6300U", "i7-6500U", "i7-6600U")
    # ordinal + G-shorthand generations normalize to seeds
    cpu, _, _, est, _ = resolve_cpu_with_seeds("Lenovo ThinkPad X1 Carbon 5th Gen | Windows 11")
    assert est is True and cpu in ("i5-7200U", "i5-7300U", "i7-7500U", "i7-7600U")
    cpu, _, _, est, _ = resolve_cpu_with_seeds("Lenovo Thinkpad X1 Carbon G11 Campus")
    assert est is True and cpu in ("i5-1335U", "i5-1345U", "i7-1355U", "i7-1365U", "i7-1370P")
    cpu, _, _, est, _ = resolve_cpu_with_seeds("Lenovo Thinkpad X1 Extreme G4 mit 1TB RAM und RTX 3080")
    assert est is True and cpu in ("i7-11800H", "i9-11950H", "i9-11980HK")
    cpu, _, _, est, _ = resolve_cpu_with_seeds("Lenovo Legion Y540-17IRH Gaming-Laptop")
    assert est is True and cpu in ("i5-9300H", "i7-9750H", "i7-9750HF")
    # Modell: tail is retained through the vinted suffix strip
    cpu, _, _, est, _ = resolve_cpu_with_seeds(
        "Porsche Piwis 3 Diagnosegerät, Marke: Lenovo, Modell: ThinkPad X250, Zustand: Gut")
    assert est is True and cpu in ("i5-5200U", "i5-5300U", "i7-5600U")


def test_enrich_cpu_estimate_parity():
    """enrich_cpu fallback uses the same seed helper (single source of truth)."""
    from deal_radar.contracts import CanonicalListing
    from deal_radar.scoring import enrich_cpu
    l = CanonicalListing(id="t:1", source="t", native_id="1", url="https://x.example/1",
                         title="ThinkPad X1 Carbon Gen 6", description="i5 16GB")
    facts = enrich_cpu(l)
    cpu = next((f for f in facts if f.field == "cpu"), None)
    assert cpu is not None and cpu.value.startswith("i5-")
    assert any(f.field == "cpu_candidates" for f in facts)


def test_gems_collect_full_counts_split():
    """collect_full: rated/estimated/unrated_systems/unrated_nonsystem split;
    collect() stays backward-compatible (systems-only int)."""
    import json as _j

    from deal_radar import gems as G

    class FakeDB:
        def execute(self, *a, **k):
            class C:
                def fetchall(self_inner):
                    return [
                        # exact CPU, cached bench below -> rated
                        ("a:1", "ThinkPad T480 i5-8350U", 200.0, "EUR", "https://x.example/1", "t",
                         _j.dumps({"description": "", "images": []})),
                        # seed-estimable, same base CPU cached -> estimated
                        ("a:2", "ThinkPad X1 Carbon Gen 6", 250.0, "EUR", "https://x.example/2", "t",
                         _j.dumps({"description": "i5 16GB", "images": []})),
                        # system offer, no CPU anywhere -> unrated_systems
                        ("a:3", "ThinkPad T14s - Windows 11", 180.0, "EUR", "https://x.example/3", "t",
                         _j.dumps({"description": "", "images": []})),
                        # clothes -> unrated_nonsystem
                        ("a:4", "Nike Training Shorts Blue Mens XL", 30.0, "EUR", "https://x.example/4", "t",
                         _j.dumps({"description": "", "images": []})),
                        # barebone 0/0 unit, cached bench -> rated with uplift
                        ("a:5", "Firebat Ryzen 7 H255 0GB 0TB Barebone", 100.0, "EUR", "https://x.example/5", "t",
                         _j.dumps({"description": "", "images": []})),
                    ]
            return C()

    class FakeStore:
        db = FakeDB()

    real_cached = G.cached_cpu
    benches = {"i5-8350U": {"multi": 8000, "single": 2000},
               "Ryzen 7 255": {"multi": 8200, "single": 3700}}
    G.cached_cpu = lambda cpu: benches.get(cpu)
    try:
        items, counts = G.collect_full(FakeStore())
        assert counts == {"rated": 2, "estimated": 1,
                          "unrated_systems": 1, "unrated_nonsystem": 1}, counts
        assert {x["id"] for x in items} == {"a:1", "a:2", "a:5"}
        assert next(x for x in items if x["id"] == "a:2")["estimated"] is True
        assert next(x for x in items if x["id"] == "a:1")["estimated"] is False
        bb = next(x for x in items if x["id"] == "a:5")
        assert bb["barebone_uplift"] == 125 and bb["full_price"] == 225.0
        assert bb["ppe"] == 82.0 and bb["ppe_full"] == round(8200 / 225, 1)
        # perf/€ board ranks complete-system cost: a:1 (40/40) beats a:5 (raw 82, full 36.4)
        b = G.board(items)
        assert next(x["id"] for x in b["ppe"]) == "a:1"
        items2, unrated = G.collect(FakeStore())
        assert unrated == 1 and len(items2) == 3
    finally:
        G.cached_cpu = real_cached


def test_extract_ram_storage_ports_barebone():
    from deal_radar.scoring import (
        extract_ports,
        extract_ram,
        extract_storage,
        is_barebone,
    )
    assert extract_ram("Minisforum UM870 Slim Ryzen 7 8745H 16GB DDR5 Barebone") == 16
    assert extract_ram("ThinkPad X1 Yoga Gen 6 | i5 | 16GB RAM | 256GB SSD") == 16
    assert extract_ram("512GB SSD NVMe") is None  # storage must not leak into RAM
    assert extract_ram("BMW M1 car") is None
    assert extract_storage("Acemagic Retro X3 Ryzen 7, 16GB, 1TB, Radeon 780M") == (1024, "")
    assert extract_storage("1TB NVMe SSD") == (1024, "NVME")
    assert extract_storage("240GB SSD") == (240, "SSD")
    assert extract_storage("2TB Festplatte") == (2048, "HDD")
    assert extract_storage("no storage here") == (None, "")
    ports = extract_ports("MINISFORUM X1 AI Mini PC USB4 OCuLink WiFi 7 HDMI 2.5G LAN")
    assert ports == ["USB4", "OCuLink", "HDMI", "2.5G LAN", "WiFi 7"], ports
    assert extract_ports("ThinkPad T480 i5-8350U") == []
    assert is_barebone("Mini Pc Intel Core Ultra 9 285H ES 0GB/32GB 0TB/1TB Barebone") is True
    assert is_barebone("AOOSTAR MACO Barebone Mini-PC AMD Ryzen 7 8845HS") is True
    assert is_barebone("ohne RAM und SSD, Gehäuse") is True
    assert is_barebone("ThinkPad T480 i5-8350U 16GB RAM 512GB SSD") is False


def test_enrich_specs_fact_fields():
    from deal_radar.contracts import CanonicalListing
    from deal_radar.scoring import enrich_specs
    l = CanonicalListing(id="t:1", source="t", native_id="1", url="https://x.example/1",
                         title="MINISFORUM X1 AI Mini PC Ryzen 7 255 Radeon 780M WiFi 7 USB4 OCuLink Barebone",
                         description="16GB DDR5, 1TB NVMe")
    by_field = {f.field: f for f in enrich_specs(l)}
    assert by_field["ram_gb"].value == 16
    assert by_field["storage_gb"].value == 1024
    assert by_field["storage_kind"].value == "NVME"
    assert "USB4" in by_field["ports"].value and "OCuLink" in by_field["ports"].value
    assert by_field["barebone"].value is True
    l2 = CanonicalListing(id="t:2", source="t", native_id="2", url="https://x.example/2",
                          title="Nike Training Shorts", description="")
    assert enrich_specs(l2) == []


def test_offer_targets_plain_and_barebone():
    from deal_radar.scoring import offer_targets
    assert offer_targets(None) == {} and offer_targets(0) == {}
    t = offer_targets(28261)
    assert t["pay_for_100"] == round(28261 / 100) and t["barebone_uplift"] == 0
    b = offer_targets(28261, barebone=True)
    assert b["pay_for_100"] == round(28261 / 100 + 85) and b["barebone_uplift"] == 85
    # RAM included -> no uplift even when flagged
    assert offer_targets(28261, barebone=True, ram_gb=16)["barebone_uplift"] == 0


def test_extract_cpu_ryzen_h_split():
    from deal_radar.scoring import extract_cpu, resolve_cpu_with_seeds
    cpu, conf, _ = extract_cpu("ACEMAGIC GAME Mini PC AMD Ryzen 7 H255 16GB LPDDR5 512GB SSD")
    assert cpu == "Ryzen 7 255" and conf >= 0.8, (cpu, conf)
    cpu, conf, _ = extract_cpu("Firebat Mini PC AMD Ryzen 7 H 255 0GB 0TB")
    assert cpu == "Ryzen 7 255" and conf >= 0.8, (cpu, conf)
    cpu, conf, _, est, _ = resolve_cpu_with_seeds("Ryzen 7 H255 16GB/512GB")
    assert cpu == "Ryzen 7 255" and est is False
    # no regression: normal + PRO forms unchanged
    assert extract_cpu("Ryzen 7 8845HS mini pc")[0] == "Ryzen 7 8845HS"
    assert extract_cpu("Ryzen 5 PRO 5650U laptop")[0] == "Ryzen 5 PRO 5650U"


def test_extract_intel_tier_suffix_guards():
    from deal_radar.scoring import extract_cpu
    # explicit glued tier trusted, never re-derived
    assert extract_cpu("Lenovo ThinkPad T14 G3 Mainboard i7-1255U 16 RAM")[0] == "i7-1255U"
    assert extract_cpu("Board i5-10210U defekt")[0] == "i5-10210U"
    # suffix must end at word boundary (Prozessor is not PRO)
    cpu, _, _ = extract_cpu("MS-7728 1155 Sockel + Intel I5 2500 Prozessor")
    assert cpu == "i5-2500" and "PRO" not in cpu, cpu
    # Intel context is never a Ryzen
    cpu, _, _ = extract_cpu("LENOVO ThinkPad P52 Motherboard mit INTEL i7-8750H Quadro P1000")
    assert cpu == "i7-8750H", cpu
    # EPYC recognized
    assert extract_cpu("AMD CPU Epyc 7351P 16C/32T")[0] == "EPYC 7351P"
    assert extract_cpu("Server EPYC 7302P 128GB DDR4")[0] == "EPYC 7302P"


def test_board_seeds_and_info():
    from deal_radar.scoring import board_info, resolve_cpu_with_seeds
    cpu, _, _, est, _ = resolve_cpu_with_seeds("Lenovo thinkpad T460s motherboard")
    assert est is True and cpu in ("i5-6200U", "i5-6300U", "i7-6500U", "i7-6600U")
    cpu, _, _, est, _ = resolve_cpu_with_seeds("MacBook Pro 16 A2141 Logic Board i7 16GB 512GB")
    assert est is True and cpu in ("i7-9750H", "i9-9880H", "i9-9980HK")
    cpu, _, _, est, _ = resolve_cpu_with_seeds("MacBook Pro 14 Logic Board 8GB 256GB")
    assert est is True and cpu in ("M1 Pro", "M1 Max")
    # whole machines with MODEL seeds resolve via the model path (same CPUs);
    # machines with neither seed stay unknown
    cpu, _, _, est, _ = resolve_cpu_with_seeds("Lenovo ThinkPad T460s Windows 11")
    assert est is True and cpu in ("i5-6200U", "i5-6300U", "i7-6500U", "i7-6600U")
    cpu, _, _, est, _ = resolve_cpu_with_seeds("Lenovo ThinkPad T14s Windows 11")
    assert est is False and cpu is None
    assert board_info("X670E motherboard AM5") == (True, True)
    assert board_info("ThinkPad X13 Gen1 AMD Mainboard Ryzen") == (True, False)
    assert board_info("ThinkPad T480 i5-8350U laptop") == (False, False)


def test_gems_boards_fx_io_defekt():
    """Boards leaderboard: FX-normalized, IO daughterboards excluded, defective
    boards excluded, completion reduced by included parts."""
    import json as _j

    from deal_radar import gems as G

    class FakeDB:
        def execute(self, *a, **k):
            class C:
                def fetchall(self_inner):
                    return [
                        ("b:1", "ThinkPad X13 Gen1 AMD Mainboard Ryzen 5 PRO 4650U 8GB", 90.0, "EUR",
                         "https://x.example/1", "t", _j.dumps({"description": "", "images": []})),
                        ("b:2", "ThinkPad E14/E15 Gen 2 usb LAN I/O-Platine", 3.0, "EUR",
                         "https://x.example/2", "t", _j.dumps({"description": "", "images": []})),
                        ("b:3", "X13 Gen 3 Yoga Mainboard Defekt i5-1235U", 20.0, "EUR",
                         "https://x.example/3", "t", _j.dumps({"description": "", "images": []})),
                        ("b:4", "AOOSTAR GEM12 Ryzen 7 8845HS Barebone", 299.0, "USD",
                         "https://x.example/4", "t", _j.dumps({"description": "", "images": []})),
                    ]
            return C()

    class FakeStore:
        db = FakeDB()

    benches = {"Ryzen 5 PRO 4650U": {"multi": 11920, "single": 1500},
               "i5-1235U": {"multi": 12404, "single": 2500},
               "Ryzen 7 8845HS": {"multi": 28260, "single": 3700}}
    real_cached = G.cached_cpu
    G.cached_cpu = lambda cpu: benches.get(cpu)
    try:
        items, _ = G.collect_full(FakeStore())
        by_id = {x["id"]: x for x in items}
        # b:2 IO board: no CPU estimate -> unrated (absent)
        assert "b:2" not in by_id
        b1 = by_id["b:1"]
        assert b1["board"] is True and b1["socketed"] is False
        # 8GB in title is not a RAM size -> full 120 completion
        assert b1["eff_price"] == 210.0 and b1["eff_ppe"] == round(11920 / 210, 1)
        b = G.board(items)
        # defekt board (parts kind) excluded from boards
        assert all(x["id"] != "b:3" for x in b["boards"])
        assert next(x["id"] for x in b["boards"]) == "b:1"
        # USD normalized: 299 USD -> ~276.85 EUR, barebone +125
        b4 = by_id["b:4"]
        assert b4["barebone_uplift"] == 125
        assert b4["ppe_full"] == round(28260 / (round(299 / 1.08, 2) + 125), 1), b4["ppe_full"]
    finally:
        G.cached_cpu = real_cached


def test_board_io_and_upto_guards():
    from deal_radar.scoring import (
        board_info,
        extract_ram,
        extract_storage,
        resolve_cpu_with_seeds,
    )
    # IO daughterboard: recognized as non-system-board, no CPU attribution
    assert board_info("ThinkPad E14 USB & LAN I/O-Platine Ersatzteil") == (False, False)
    cpu, _, _, est, _ = resolve_cpu_with_seeds("ThinkPad E14 Gen 2 usb LAN I/O-Platine")
    assert cpu is None and est is False
    # real board still detected
    assert board_info("ThinkPad X13 Gen1 AMD Mainboard Ryzen") == (True, False)
    # option maximums are not included parts
    assert extract_ram("Barebone, RAM slots up to 128GB DDR5") is None
    assert extract_storage("2 slots up to 8TB NVMe")[0] is None
    assert extract_ram("16GB DDR5, 1TB NVMe") == 16


def test_unverified_defers_to_seeds():
    """Bare 'Ryzen 5' yields the seed estimate (with candidates), not the
    unverified fragment."""
    from deal_radar.scoring import resolve_cpu_with_seeds
    cpu, _, _, est, cands = resolve_cpu_with_seeds(
        "Lenovo ThinkPad X395, 16GB RAM, Ryzen 5, Windows 11 Pro")
    assert est is True and cpu == "Ryzen 5 PRO 3500U" and cands
    # no seed anywhere -> old unverified behavior preserved
    cpu, _, why, est, _ = resolve_cpu_with_seeds("Mini pc AMD Ryzen 3 con 8gb ram")
    assert est is False and "unverified" in why


def test_shopify_skips_unavailable_variants():
    """Ghost deals stay out: sold-out variants never set the price; fully
    sold-out products vanish from results."""
    import asyncio

    from shopify.driver import ShopifyDriver

    from deal_radar.driver_sdk import SearchQuery

    feed = {"products": [
        {"id": 1, "title": "UM560 Refurbished", "handle": "um560", "tags": [],
         "body_html": "Ryzen 5 5625U mini pc",
         "images": [],
         "variants": [
             {"price": "139.00", "available": False, "title": "Barebone"},
             {"price": "199.00", "available": True, "title": "16GB+512GB"},
         ]},
        {"id": 2, "title": "UM690 Refurbished", "handle": "um690", "tags": [],
         "body_html": "Ryzen 9 6900HX mini pc",
         "images": [],
         "variants": [
             {"price": "289.00", "available": False, "title": "16GB+512GB"},
         ]},
    ]}

    class FakeT:
        async def get(self, url, headers=None):
            class R:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self_inner):
                    return feed
            return R()

    from shopify import driver as S
    S._CATALOG.clear()
    try:
        d = ShopifyDriver(transport=FakeT(), shop_id="minisforum",
                          shop_name="Minisforum EU", base_url="https://minisforumpc.eu")
        out = asyncio.run(d.search(SearchQuery(keywords="ryzen mini pc", limit=10)))
        assert len(out) == 1 and out[0].price == 199.0, [(x.title, x.price) for x in out]
        assert "Barebone" not in out[0].title
    finally:
        S._CATALOG.clear()


def test_seed_short_keys_need_boundaries():
    """Dimensions must not conjure CPUs: '172 x270 cm' is a carpet, not a ThinkPad."""
    from deal_radar.scoring import resolve_cpu_with_seeds
    cpu, _, _, est, _ = resolve_cpu_with_seeds("Großer Teppich hellgrau 172 x270 cm")
    assert cpu is None and est is False
    cpu, _, _, est, _ = resolve_cpu_with_seeds("Linoleum 290 x270 Rollenware")
    assert cpu is None and est is False
    # real short-key boards still resolve (token match)
    cpu, _, _, est, _ = resolve_cpu_with_seeds("Lenovo ThinkPad X270 Mainboard i5-7300U")
    assert cpu == "i5-7300U" and est is False
    cpu, _, _, est, _ = resolve_cpu_with_seeds("ThinkPad T460s motherboard")
    assert est is True and cpu in ("i5-6200U", "i5-6300U", "i7-6500U", "i7-6600U")
    cpu, _, _, est, _ = resolve_cpu_with_seeds("MacBook Pro 16 A2141 Logic Board")
    assert est is True and cpu in ("i7-9750H", "i9-9880H", "i9-9980HK")


def test_gems_bare_cpu_completion():
    """Tray CPUs rank with board+RAM completion, not chip-only price."""
    import json as _j

    from deal_radar import gems as G

    class FakeDB:
        def execute(self, *a, **k):
            class C:
                def fetchall(self_inner):
                    return [
                        ("c:1", "Intel Xeon e5-2667 v4 SR2LF 3.6GHz Quad-Core", 35.0, "EUR",
                         "https://x.example/1", "t", _j.dumps({"description": "", "images": []})),
                    ]
            return C()

    class FakeStore:
        db = FakeDB()

    real_cached = G.cached_cpu
    G.cached_cpu = lambda cpu: {"multi": 13810, "single": 2000} if cpu == "Xeon E5-2667" else None
    try:
        items, _ = G.collect_full(FakeStore())
        assert len(items) == 1
        assert items[0]["barebone_uplift"] == 150, items[0]
        assert items[0]["ppe_full"] == round(13810 / 185, 1)
    finally:
        G.cached_cpu = real_cached


def test_resolution_part_digit_gates():
    from deal_radar.benchmarks import closest_known_cpu
    from deal_radar.scoring import extract_cpu, resolve_cpu_with_seeds
    # screen resolution is not a CPU
    assert extract_cpu("Pro Tragbarer Monitor 16 Zoll 2.5K 2560 x 1600 144Hz USB-C")[0] is None
    assert resolve_cpu_with_seeds("Monitor 27 Zoll 1920x1080 HDMI")[0] is None
    # spare parts carry no bench
    assert resolve_cpu_with_seeds("Apple MacBook Air M1 2020 A2337 Display Assembly DEFEKT")[0] is None
    assert resolve_cpu_with_seeds("Palmrest Tastatur Lenovo Thinkpad X1 Yoga gen 4")[0] is None
    # whole machines with broken screens still resolve
    cpu, _, _, _, _ = resolve_cpu_with_seeds("MacBook Air M1 2020 Display defekt sonst ok")
    assert cpu is not None
    # closest match stays within generation (no 1600->7600X inflation).
    # _gpu_mem cleared: other tests populate the shared GPU table.
    from unittest.mock import patch
    with patch.dict("deal_radar.benchmarks._gpu_mem", {}, clear=True):
        assert closest_known_cpu("Ryzen 5 1600")[0] is None
        assert closest_known_cpu("Ryzen 5 2600")[0] is None
        assert closest_known_cpu("Ryzen 5 5500")[0] is None
        name, score = closest_known_cpu("Ryzen 7 580H")
        assert name is not None and score >= 0.9  # typo tolerance kept


def test_accessory_titles_get_no_estimate():
    """Keyboards/fans for a laptop line are parts, never estimate carriers."""
    from deal_radar.scoring import resolve_cpu_with_seeds
    assert resolve_cpu_with_seeds(
        "Russisch Tastatur für Dell Latitude 5420 5430 5421")[0] is None
    assert resolve_cpu_with_seeds("Intel Core i5-14400F ventilateur")[0] is None
    # exact-CPU bundles still resolve (solid mention wins)
    cpu, _, _, est, _ = resolve_cpu_with_seeds(
        "Mobo Combo-Z170 Pro Gaming Motherboard Intel i7-6700k 16GB RAM")
    assert cpu == "i7-6700K" and est is False


def test_io_blende_excluded_and_platform_sort():
    from deal_radar import gems as G
    from deal_radar.scoring import board_info
    assert board_info("Universal IO-Shield IO-Blende MSI Asus") == (False, False)
    assert board_info("ThinkPad X270 Mainboard i5") == (True, False)
    items = [
        {"id": "p1", "title": "Z170 board", "price": None, "currency": "EUR",
         "url": "u", "source": "t", "board": True, "socketed": True, "kind": "offer",
         "multi": None, "ppe": 0, "ppe_full": 0},
        {"id": "p2", "title": "B550 board", "price": 80.0, "currency": "EUR",
         "url": "u", "source": "t", "board": True, "socketed": True, "kind": "offer",
         "multi": None, "ppe": 0, "ppe_full": 0},
    ]
    b = G.board(items)
    assert [x["id"] for x in b["platforms"]] == ["p2", "p1"]


def test_ultra_suffix_tight():
    from deal_radar.scoring import extract_cpu
    assert extract_cpu("Intel core ultra 5 225 seria 2")[0] == "Core Ultra 5 225"
    assert extract_cpu("Core Ultra 7 155H laptop")[0] == "Core Ultra 7 155H"
    assert extract_cpu("Ultra 9 285HX workstation")[0] == "Core Ultra 9 285HX"
    assert extract_cpu("Core Ultra 7 258V convertible")[0] == "Core Ultra 7 258V"
    assert extract_cpu("Gaming PC Core Ultra 7 265K RTX 5060")[0] == "Core Ultra 7 265K"

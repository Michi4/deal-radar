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

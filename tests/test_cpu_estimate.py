"""Family estimates for vague CPU mentions (honest best-effort, labeled)."""
from deal_radar.contracts import CanonicalListing, Seller
from deal_radar.scoring import MODEL_CPU_SEED, enrich_cpu


def _mk(title):
    return CanonicalListing(id="t", source="t", native_id="t", url="https://x.test",
                            title=title, description="top", price=500.0,
                            seller=Seller(name="s"))


def test_seed_hits_estimate():
    fs = enrich_cpu(_mk("Lenovo ThinkPad X1 Carbon Gen 6 i5"))
    assert fs and fs[0].field == "cpu" and fs[0].value == "i5-8350U"
    assert fs[0].confidence < 0.7
    assert "estimate" in fs[0].sources[0].detail


def test_nospace_variant_matches():
    fs = enrich_cpu(_mk("lenovo thinkpad x1 carbon gen6"))
    assert fs and fs[0].value == "i5-8350U"


def test_truly_unknown_stays_empty():
    assert enrich_cpu(_mk("vague laptop thing")) == []
    assert enrich_cpu(_mk("Thinkpad Yoga X1, 8GB")) == []


def test_exact_still_wins():
    fs = enrich_cpu(_mk("ThinkPad with Ryzen 5 PRO 5650U notebook"))
    assert fs and "ryzen" in fs[0].value.lower() and fs[0].confidence > 0
    assert "family estimate" not in fs[0].sources[0].detail
    assert fs[0].value == "Ryzen 5 PRO 5650U"  # normalized, PRO kept


def test_seed_sanity_spot():
    assert MODEL_CPU_SEED["thinkpad x1 carbon gen 6"] == ["i5-8350U", "i7-8650U"]
    assert MODEL_CPU_SEED["macbook air m2"] == ["M2"]


def test_m2_ssd_not_apple_silicon():
    from deal_radar.scoring import extract_cpu
    assert extract_cpu("mainboard x1 carbon m.2 ssd slot".lower())[0] is None
    assert extract_cpu("thinkpad mit m2 2280 ssd".lower())[0] is None
    assert extract_cpu("macbook air m1 2020 mit 512gb ssd".lower())[0] == "m1"
    assert extract_cpu("macbook pro m2".lower())[0] == "m2"


def test_minipc_cpu_patterns():
    from deal_radar.scoring import extract_cpu
    assert extract_cpu("topc mini pc ultra 5 235h es".lower())[0] == "Core Ultra 5 235H"
    assert extract_cpu("core ultra 7 155h 32gb".lower())[0] == "Core Ultra 7 155H"
    assert extract_cpu("ryzen ai 9 hx 370 mini".lower())[0] == "Ryzen AI 9 HX 370"
    assert extract_cpu("ryzen ai 7 pro 350".lower())[0] == "Ryzen AI 7 PRO 350"
    assert extract_cpu("beelink 8845hs".lower())[0] == "Ryzen 7 8845HS"
    assert extract_cpu("r7 7840u 32gb".lower())[0] == "Ryzen 7 7840U"
    assert extract_cpu("ryzen 5 7640u".lower())[0] == "Ryzen 5 7640U"
    assert extract_cpu("ryzen 9 7940hs".lower())[0] == "Ryzen 9 7940HS"
    assert extract_cpu("mini pc i7 12700h".lower())[0] == "i7-12700H"
    assert extract_cpu("intel i5-12450h".lower())[0] == "i5-12450H"
    # storage numbers are not CPUs
    assert extract_cpu("512gb ssd 16gb ram".lower())[0] is None
    assert extract_cpu("laptop 2024 modell".lower())[0] is None


def test_es_sample_risk():
    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.risk_engine import assess_risk
    mk = lambda t: CanonicalListing(id="t", source="t", native_id="t", url="u", title=t,
                                    description="top zustand", price=270.0, seller=Seller(name="s"))
    r = assess_risk(mk("TOPC Mini PC Ultra 5 235H ES barebone"))
    assert r.score >= 0.25 and any("engineering" in x for x in r.reasons)
    r2 = assess_risk(mk("Beelink 8845HS 24GB 1TB"))
    assert not any("engineering" in x for x in r2.reasons)


def test_no_more_apple_false_positives():
    from deal_radar.scoring import extract_cpu
    assert extract_cpu("bmw m1 coupe modellauto 1:87")[0] is None
    assert extract_cpu("peaq mini pc m100 windows")[0] is None
    assert extract_cpu("igel m330c minipc")[0] is None
    assert extract_cpu("acemagic am18 7840hs")[0] == "Ryzen 7 7840HS"
    assert extract_cpu("thinkcentre m72e 3267-5m4")[0] is None
    assert extract_cpu("macbook air m1 2020")[0] == "m1"
    assert extract_cpu("macbook pro m2")[0] == "m2"


def test_ryzen_desktop_and_r3():
    from deal_radar.scoring import extract_cpu
    assert extract_cpu("msi pro dp20z ryzen 5 5600g")[0] == "Ryzen 5 5600G"
    assert extract_cpu("ryzen 7 5700g 32gb")[0] == "Ryzen 7 5700G"
    assert extract_cpu("thinkcentre ryzen 7 pro 4750ge")[0] == "Ryzen 7 PRO 4750GE"
    assert extract_cpu("soyo m5 ryzen 3 4300u")[0] == "Ryzen 3 4300U"
    assert extract_cpu("ryzen 5 5500u 16gb")[0] == "Ryzen 5 5500U"


def test_storage_size_m2_rejected():
    from deal_radar.scoring import extract_cpu
    assert extract_cpu("hp 260 g3 mini pc, 8gb ram, 256 m2")[0] is None
    assert extract_cpu("laptop 512 m2 ssd")[0] is None
    assert extract_cpu("macbook air m2 2020 256gb")[0] == "m2"


def test_igpu_patterns():
    from deal_radar.scoring import extract_gpu
    assert extract_gpu("intel arc 140t igpu")[0] == "arc 140t"
    assert extract_gpu("arc 130v graphics")[0] == "arc 130v"
    assert extract_gpu("radeon 780m")[0] == "radeon 780m"
    assert extract_gpu("ryzen 7 7840hs radeon 780m")[0] == "radeon 780m"
    assert extract_gpu("ryzen 5 5600g vega 7")[0] == "vega 7"
    _, conf, _ = extract_gpu("rx vega 11")
    assert conf >= 0.7


def test_spec_line_cpu_fallback_and_gpu():
    from deal_radar.contracts import CanonicalListing, Seller
    from deal_radar.orchestrator import spec_line
    mk = lambda t, d="": CanonicalListing(id="t", source="t", native_id="t", url="u",
                                          title=t, description=d, price=100.0,
                                          seller=Seller(name="s"))
    # CPU recovered from text when no fact present (marked uncertain)
    assert "Ryzen 7 8845HS (?)" in spec_line(mk("Beelink 8845HS 24GB"), [])
    # storage sizes are not CPUs (but still shown as specs)
    only_storage = spec_line(mk("ThinkPad X395 8GB RAM 238GB SSD", "512GB Speichermedien"), [])
    assert "CPU" not in only_storage and "238GB SSD" in only_storage
    # gpu + G3D shown when present
    txt = spec_line(mk("Mini PC", "arc 140t"), [{"field": "gpu", "value": "arc 140t"},
                                                {"field": "gpu_benchmark", "value": 5000}])
    assert "arc 140t" in txt and "5000 G3D" in txt

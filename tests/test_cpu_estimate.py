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
    assert fs and "ryzen" in fs[0].value and fs[0].confidence > 0
    assert "family estimate" not in fs[0].sources[0].detail


def test_seed_sanity_spot():
    assert MODEL_CPU_SEED["thinkpad x1 carbon gen 6"] == ["i5-8350U", "i7-8650U"]
    assert MODEL_CPU_SEED["macbook air m2"] == ["M2"]

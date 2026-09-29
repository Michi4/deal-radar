"""Blacklist entries always mean exclusion, however the caller words the op."""
from deal_radar.contracts import CanonicalListing
from deal_radar.filter_engine import apply_filters, eval_rule


def _listing(title):
    return CanonicalListing(id="t", source="t", native_id="t", url="https://x.test",
                            title=title, description="phone in top condition " * 5,
                            price=500.0, images=[])


def test_positive_op_in_blacklist_excludes():
    phone = _listing("iPhone 15 Pro 128GB Top")
    for op, val in (("contains", "iPhone"), ("regex", "iPhone.*"),
                      ("equals", "iPhone 15 Pro 128GB Top")):
        r = apply_filters(phone, {}, [{"fields": ["title"], "op": op, "value": val}])
        assert not r.passed, op
    r = apply_filters(phone, {}, [{"fields": ["title"], "op": "contains", "value": "Hülle"}])
    assert r.passed


def test_not_equals_op():
    ok, _, _ = eval_rule(_listing("defekt"), {"fields": ["title"], "op": "not_equals", "value": "defekt"})
    assert not ok
    ok, _, _ = eval_rule(_listing("Top Zustand"), {"fields": ["title"], "op": "not_equals", "value": "defekt"})
    assert ok

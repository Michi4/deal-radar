"""Per-field hard filter engine. Missing fields never error — rule is skipped as N/A."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .contracts import CanonicalListing


@dataclass
class FilterResult:
    passed: bool
    reasons: list[str]
    missing_fields: list[str]


SUPPORTED_OPS = {"contains", "not_contains", "regex", "not_regex", "equals",
                 "lt", "gt", "range", "in", "not_in", "exists"}


def _matchable_fields(listing: CanonicalListing) -> dict[str, str]:
    return {
        "title": listing.title or "",
        "description": listing.description or "",
        "tags": " ".join(listing.tags or []),
        "category": listing.category or "",
        "seller_name": listing.seller.name if listing.seller else "",
        "location": listing.location or "",
        "postcode": listing.postcode or "",
        "shipping": listing.shipping or "",
        "condition": listing.condition or "",
        "ocr": "\n".join(listing.ocr_texts or []),
        "all_text": listing.field_text("all_text"),
        "url": listing.url or "",
    }


def eval_rule(listing: CanonicalListing, rule: dict[str, Any]) -> tuple[bool, str, bool]:
    """Returns (passed, reason, was_missing). Missing/empty field -> (True, 'N/A', True)."""
    fields: list[str] = rule.get("fields") or ([rule["field"]] if "field" in rule else ["all_text"])
    op: str = rule.get("op", "contains")
    pat: str = str(rule.get("value", rule.get("pattern", "")))
    matched_any_field = False
    field_map = _matchable_fields(listing)
    # attributes.* support
    extra = {}
    if any(f.startswith("attributes.") for f in fields):
        for f in fields:
            if f.startswith("attributes."):
                extra[f] = listing.field_text(f)
        field_map.update(extra)

    # numeric special-cases (price, distance_km, shipping_cost)
    for num_field in ("price", "distance_km", "shipping_cost"):
        if num_field in fields:
            val = {"price": listing.price, "distance_km": listing.distance_km,
                   "shipping_cost": listing.shipping_cost}[num_field]
            if val is None:
                return True, f"{num_field} missing -> rule N/A", True
            try:
                if op == "lt":
                    ok = val < float(rule["value"])
                elif op == "gt":
                    ok = val > float(rule["value"])
                elif op == "range":
                    ok = float(rule.get("min", 0)) <= val <= float(rule.get("max", 1e18))
                elif op == "equals":
                    ok = val == float(rule["value"])
                else:
                    return True, f"op {op} N/A for {num_field}", True
                return ok, f"{num_field} {val} {op} {rule.get('value', '')} -> {'pass' if ok else 'fail'}", False
            except (ValueError, KeyError):
                return True, f"{num_field} rule malformed -> N/A", True

    # boolean delivery flags: {field: pickup|shipping_available, op: equals, value: true/false}
    for bool_field, actual in (("pickup", listing.pickup_available),
                               ("pickup_available", listing.pickup_available),
                               ("shipping_available", listing.shipping_available)):
        if bool_field in fields:
            want = rule.get("value", True)
            want_b = str(want).lower() in ("1", "true", "yes") if isinstance(want, str) else bool(want)
            ok = actual == want_b
            return ok, f"{bool_field}={actual} vs wanted {want_b} -> {'pass' if ok else 'fail'}", False

    for f in fields:
        text = field_map.get(f, "")
        if not text:
            continue  # missing on this listing -> try next field
        matched_any_field = True
        t = text
        tl, pl = t.lower(), pat.lower()
        if op == "contains":
            if pl in tl:
                return True, f"{f} contains '{pat}'", False
        elif op == "not_contains":
            if pl in tl:
                return False, f"{f} contains blacklisted '{pat}'", False
        elif op == "regex":
            if re.search(pat, t, re.IGNORECASE):
                return True, f"{f} regex '{pat}' matched", False
        elif op == "not_regex":
            if re.search(pat, t, re.IGNORECASE):
                return False, f"{f} regex '{pat}' hit blacklist", False
        elif op == "equals":
            if tl.strip() == pl.strip():
                return True, f"{f} equals '{pat}'", False
        elif op == "in":
            vals = rule.get("values", [])
            if any(str(v).lower() in tl for v in vals):
                return True, f"{f} in {vals}", False
        elif op == "not_in":
            vals = rule.get("values", [])
            if any(str(v).lower() in tl for v in vals):
                return False, f"{f} in blacklist {vals}", False
        elif op == "exists":
            return True, f"{f} exists", False
    if not matched_any_field:
        return True, f"fields {fields} missing -> N/A", True
    # fell through: for positive ops -> fail; for negative ops -> pass
    if op in ("contains", "regex", "equals", "in", "exists"):
        return False, f"required '{pat}' not found in {fields}", False
    return True, "blacklist clean", False


def apply_filters(listing: CanonicalListing, hard: dict[str, Any] | None,
                  blacklist: list[dict] | None = None,
                  whitelist: list[dict] | None = None) -> FilterResult:
    reasons: list[str] = []
    missing: list[str] = []
    hard = hard or {}
    # price bounds shorthand
    if hard.get("max_price") is not None and listing.price is not None and listing.price > float(hard["max_price"]):
        return FilterResult(False, [f"price {listing.price} > max {hard['max_price']}"], missing)
    if hard.get("min_price") is not None and listing.price is not None and listing.price < float(hard["min_price"]):
        return FilterResult(False, [f"price {listing.price} < min {hard['min_price']}"], missing)
    for rule in (blacklist or []):
        ok, reason, was_missing = eval_rule(listing, rule)
        if was_missing:
            missing.append(reason)
            continue
        if not ok:
            return FilterResult(False, [f"BLACKLIST: {reason}"], missing)
    if whitelist:
        any_pass = False
        for rule in whitelist:
            ok, reason, was_missing = eval_rule(listing, rule)
            if was_missing:
                missing.append(reason)
                continue
            if ok:
                any_pass = True
                reasons.append(f"WHITELIST: {reason}")
                break
        if not any_pass:
            # if all whitelist rules were N/A (missing fields) -> pass, else fail
            if len(missing) >= len(whitelist):
                reasons.append("whitelist N/A (missing fields) -> pass")
            else:
                return FilterResult(False, ["whitelist: no rule matched"], missing)
    for rule in hard.get("rules", []) or []:
        ok, reason, was_missing = eval_rule(listing, rule)
        if was_missing:
            missing.append(reason)
            continue
        if not ok:
            return FilterResult(False, [f"HARD: {reason}"], missing)
        reasons.append(f"HARD ok: {reason}")
    if not reasons:
        reasons.append("passed (no applicable rules)")
    return FilterResult(True, reasons, missing)

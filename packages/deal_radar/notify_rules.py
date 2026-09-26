"""Per-watch notification rules shared by orchestrator (price events) and API watcher (new matches)."""
from __future__ import annotations


def rule_ok(rule: dict, kind: str, r: dict | None = None, ev: dict | None = None) -> bool:
    """{"kind": "new_match"|"price_drop", "min_score": 0..1, "max_risk": 0..1,
    "min_drop_pct": 0..100}. All set constraints must hold."""
    if rule.get("kind", kind) != kind:
        return True  # rule targets another kind; doesn't veto
    if r is not None:
        if "min_score" in rule and r.get("final_score", 0) < float(rule["min_score"]):
            return False
        if "max_risk" in rule and r.get("risk", {}).get("score", 0) > float(rule["max_risk"]):
            return False
    if ev is not None and "min_drop_pct" in rule:
        try:
            old, new = float(ev.get("old", 0)), float(ev.get("new", 0))
            drop = (old - new) / old * 100 if old > 0 else 0
        except (ValueError, TypeError):
            drop = 0
        if drop < float(rule["min_drop_pct"]):
            return False
    return True


def rules_ok(rules: list | None, kind: str, r: dict | None = None, ev: dict | None = None) -> bool:
    mine = [x for x in (rules or []) if x.get("kind", kind) == kind]
    if not mine:
        return True
    return all(rule_ok(x, kind, r, ev) for x in mine)

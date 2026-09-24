"""Risk engine: percentage + evidence, never boolean. Rescue lane so good deals survive."""
from __future__ import annotations
from .contracts import CanonicalListing, RiskAssessment

SUSPICIOUS_PHRASES = ["vorkasse", "western union", "crypto", "bitcoin", "whatsapp only",
                      "off-platform", "ausserhalb", "schnell zahlen", "druck", "geschenkkarte",
                      "gift card", "moneygram", "pay now or"]
STOCK_HINTS = ["stock photo", "stockfoto", "beispielfoto", "symbolfoto", "archivbild"]


def assess_risk(listing: CanonicalListing, market_median: float | None = None) -> RiskAssessment:
    score = 0.0
    reasons: list[str] = []
    counter: list[str] = []

    text = f"{listing.title}\n{listing.description}".lower()
    for phrase in SUSPICIOUS_PHRASES:
        if phrase in text:
            score += 0.25
            reasons.append(f"suspicious payment/pressure wording: '{phrase}'")
    for hint in STOCK_HINTS:
        if hint in text:
            score += 0.15
            reasons.append(f"stock-photo disclaimer: '{hint}'")

    if listing.price is not None and market_median:
        if market_median > 0 and listing.price < market_median * 0.5:
            score += 0.30
            reasons.append(f"price {listing.price} is >50% below median {market_median:.0f}")
        elif market_median > 0 and listing.price < market_median * 0.7:
            score += 0.12
            reasons.append(f"price {listing.price} is >30% below median {market_median:.0f}")

    if not listing.images:
        score += 0.10
        reasons.append("no images provided")
    if len(listing.description or "") < 30:
        score += 0.08
        reasons.append("very short description (<30 chars)")
    if listing.seller and listing.seller.account_age_days is not None and listing.seller.account_age_days < 14:
        score += 0.12
        reasons.append(f"new seller account ({listing.seller.account_age_days}d)")
    # counter-evidence (keeps calibration honest, feeds rescue lane)
    if listing.seller and (listing.seller.rating or 0) >= 4.5:
        counter.append(f"seller rating {listing.seller.rating} is high")
        score -= 0.05
    if "abholung" in text or "pickup" in text or "selbstabholung" in text:
        counter.append("local pickup available")
        score -= 0.05
    if len(listing.images) >= 4:
        counter.append(f"{len(listing.images)} real-looking images")
        score -= 0.03
    if len(listing.description or "") > 300:
        counter.append("detailed description")
        score -= 0.02

    score = max(0.0, min(1.0, score))
    # confidence: stronger when we have both text and images
    confidence = 0.5
    if listing.images:
        confidence += 0.15
    if len(listing.description or "") > 100:
        confidence += 0.15
    if market_median:
        confidence += 0.1
    confidence = min(0.95, confidence)
    severity = "low" if score < 0.35 else ("medium" if score < 0.65 else "high")
    return RiskAssessment(score=round(score, 3), confidence=round(confidence, 3),
                          severity=severity, reasons=reasons, counter_evidence=counter)


def apply_risk_policy(risk: RiskAssessment, value_score: float,
                      policy: dict | None = None) -> str:
    """Returns lane: top|good|review|risky|hidden. Never auto-deletes; hidden is filterable."""
    p = policy or {}
    warn = float(p.get("warning_threshold", 0.35))
    block = float(p.get("block_threshold", 0.85))
    never_block_without_hard = bool(p.get("never_block_without_hard_signal", True))
    rescue_discount = float(p.get("rescue_great_deal_below_median_pct", 0.30))
    _ = rescue_discount  # used by orchestrator via value_score; kept for config compat
    s = risk.score
    if s >= block:
        if never_block_without_hard and not risk.reasons:
            return "review"
        # rescue lane: exceptional value + high risk -> review, not hidden
        if value_score >= 0.85:
            return "review"
        return "hidden" if bool(p.get("hard_filter_enabled", False)) else "risky"
    if s >= warn:
        return "review" if value_score >= 0.7 else "risky"
    return "top" if value_score >= 0.75 else "good"

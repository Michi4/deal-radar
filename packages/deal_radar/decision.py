"""Decision cascade: cheap heuristic (Stage A, every listing) -> Jev/Kev/LLM (Stage B, borderline only).

SystemOne interface matches TypeSafe Jev API shape:
  state: dict/str, questions: {id: {type: noul|choice|score, instructions, criteria}}
so Jev (hosted), Kev (self-hosted, Apache-2.0) and heuristics are interchangeable.
"""
from __future__ import annotations
import os
from typing import Any
import httpx

JEV_API_URL = os.getenv("JEV_API_URL", "https://api.typesafe.ai/v1/systemone/decide")
KEV_URL = os.getenv("KEV_URL", "")  # e.g. http://localhost:8001/v1/systemone/decide


async def jev_decide(state: dict | str, questions: dict, model: str = "jev-latest",
                     api_key: str = "") -> dict | None:
    if not api_key:
        return None
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.post(JEV_API_URL, headers={"Authorization": f"Bearer {api_key}"},
                             json={"state": state, "questions": questions, "model": model})
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


async def kev_decide(state: dict | str, questions: dict) -> dict | None:
    if not KEV_URL:
        return None
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.post(KEV_URL, json={"state": state, "questions": questions, "model": "kev-latest"})
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


def heuristic_decide(title: str, description: str, price: float | None,
                     keywords: str) -> dict[str, Any]:
    """Stage A: deterministic, offline, ~µs. Returns match 0..1 + flags."""
    from rapidfuzz import fuzz
    kw = [k for k in keywords.lower().split() if k]
    hay = f"{title}\n{description}".lower()
    if not kw:
        token_score = 0.5
    else:
        hits = sum(1 for k in kw if k in hay)
        token_score = hits / max(1, len(kw))
    fuzzy = fuzz.token_set_ratio(keywords.lower(), f"{title}".lower()) / 100.0 if keywords else 0.5
    match = round(0.6 * token_score + 0.4 * fuzzy, 3)
    low_info = len(description or "") < 40
    return {"match": match, "fuzzy": round(fuzzy, 3), "low_info": low_info,
            "needs_stage_b": bool(0.35 <= match <= 0.75 or low_info)}


STAGE_B_QUESTIONS = {
    "is_exact_product": {"type": "noul", "instructions": "Is the listing the exact requested product (not accessory/parts/repair)?",
                         "criteria": {"true": "exact product", "false": "accessory, parts, repair or wrong item"}},
    "image_matches": {"type": "noul", "instructions": "Do the images plausibly show the described item?",
                      "criteria": {"true": "consistent", "false": "stock photo, mismatch or no evidence"}},
    "scam_risk": {"type": "score", "instructions": "How risky does this listing look?",
                  "criteria": ["no risk", "low risk", "medium risk", "high risk", "very high risk"]},
    "condition": {"type": "score", "instructions": "How good is the apparent condition?",
                  "criteria": ["broken", "poor", "fair", "good", "like new"]},
}


def stage_b_to_scores(answer: dict | None) -> dict[str, float]:
    if not answer:
        return {}
    out: dict[str, float] = {}
    try:
        ans = answer.get("answers", answer)
        if "is_exact_product" in ans:
            out["exact"] = float(ans["is_exact_product"].get("noul", 0.5))
        if "scam_risk" in ans:
            # score 0..4 -> risk 0..1
            out["risk_ai"] = float(ans["scam_risk"].get("score", 2)) / 4.0
        if "condition" in ans:
            out["condition_ai"] = float(ans["condition"].get("score", 2)) / 4.0
    except Exception:
        pass
    return out

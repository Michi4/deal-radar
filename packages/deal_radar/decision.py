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


CLOUD_API_URL = os.getenv("CLOUD_API_URL", "")  # OpenAI-compatible base, e.g. https://openrouter.ai/api/v1
CLOUD_API_KEY = os.getenv("CLOUD_API_KEY", "")
CLOUD_MODEL = os.getenv("CLOUD_MODEL", "")
CLOUD_MODELS = [m.strip() for m in os.getenv(
    "CLOUD_MODELS",
    "nvidia/nemotron-3-super-120b-a12b:free,qwen/qwen3.8-27b:free,"
    "google/gemma-4-31b-it:free,z-ai/glm-5.2:free").split(",") if m.strip()]
if CLOUD_MODEL and CLOUD_MODEL not in CLOUD_MODELS:
    CLOUD_MODELS.insert(0, CLOUD_MODEL)


async def cloud_json(system: str, user: str, max_tokens: int = 600) -> dict | None:
    """Generic OpenAI-compatible JSON call with model failover. None when unconfigured/failing (offline-first)."""
    if not (CLOUD_API_URL and CLOUD_API_KEY):
        return None
    import json as _json
    last_err: str = ""
    for model in CLOUD_MODELS:
        try:
            async with httpx.AsyncClient(timeout=60.0) as c:
                r = await c.post(f"{CLOUD_API_URL.rstrip('/')}/chat/completions",
                                 headers={"Authorization": f"Bearer {CLOUD_API_KEY}"},
                                 json={"model": model,
                                       "messages": [{"role": "system", "content": system},
                                                    {"role": "user", "content": user}],
                                       "response_format": {"type": "json_object"},
                                       "temperature": 0.2, "max_tokens": max_tokens})
                if r.status_code == 429:
                    last_err = f"{model}: 429"
                    continue
                r.raise_for_status()
                return _json.loads(r.json()["choices"][0]["message"]["content"])
        except Exception as e:  # noqa: BLE001 - try next model
            last_err = f"{model}: {e}"
            continue
    print(f"[cloud] all models failed ({last_err})", flush=True)
    return None


NL_SYSTEM = ("You convert a natural-language second-hand search into a JSON SearchIntent. "
             "Return ONLY JSON with keys: keywords (core product words for marketplace search), "
             "category, hard {max_price, min_price, rules[]}, blacklist[] ({fields,op,value}), "
             "attributes {} (inferred requirements like connector:usb-c, display:oled), "
             "risk_note. Rules use {field,op,value} with op in contains,not_contains,regex,lt,gt,range,equals. "
             "Example: 'iphone which uses a usb c plug to charge' -> "
             '{"keywords":"iphone","attributes":{"connector":"usb-c"},"hard":{"rules":[{"field":"all_text","op":"contains","value":"usb"}]}}. '
             "Never invent prices. Missing info -> omit the key.")


async def nl_to_intent(text: str) -> dict:
    """Natural language -> SearchIntent. Cloud model when configured, deterministic fallback otherwise."""
    cloud = await cloud_json(NL_SYSTEM, text)
    if cloud and isinstance(cloud.get("keywords"), str):
        return {"keywords": cloud["keywords"], "category": cloud.get("category", ""),
                "hard": cloud.get("hard", {}), "blacklist": cloud.get("blacklist", []),
                "whitelist": [], "attributes": cloud.get("attributes", {}),
                "risk": {}, "enrich": True, "limit": 20}
    return nl_fallback(text)


def nl_fallback(text: str) -> dict:
    """Offline NL parse: prices, exclusions, quoted phrases, attribute hints. No AI needed."""
    import re
    t = text
    tl = t.lower()
    hard: dict = {"rules": []}
    m = re.search(r"(?:unter|max|bis|<=?)\s*(\d[\d\.\s]*)\s*€?", tl)
    if m:
        try:
            hard["max_price"] = float(m.group(1).replace(".", "").replace(" ", ""))
        except ValueError:
            pass
    m = re.search(r"(?:über|min|ab|>=?)\s*(\d[\d\.\s]*)\s*€?", tl)
    if m and "unter" not in tl and "max" not in tl:
        try:
            hard["min_price"] = float(m.group(1).replace(".", "").replace(" ", ""))
        except ValueError:
            pass
    blacklist: list[dict] = []
    for cue in re.finditer(r"(?:ohne|kein(?:e|er)?|nicht|ausschlie[ßs]en|no)\s+([a-zäöüß\- ]{2,30}?)(?:,| und | oder |$)", tl):
        blacklist.append({"fields": ["title", "description"], "op": "not_contains",
                          "value": cue.group(1).strip()})
    attrs: dict = {}
    if re.search(r"usb[\s\-]?c", tl):
        attrs["connector"] = "usb-c"
        hard["rules"].append({"field": "all_text", "op": "regex", "value": r"usb[\s\-]?c|typ\s*c"})
    if "oled" in tl:
        attrs["display"] = "oled"
    if "lightning" in tl:
        attrs["connector"] = "lightning"
    # core keywords: strip price/exclusion/connector clauses
    kw = re.sub(r"(unter|max|bis|über|min|ab)\s*\d[\d\.\s]*\s*€?", " ", tl)
    kw = re.sub(r"(ohne|keine?r?|nicht|ausschlie[ßs]en)\s+[a-zäöüß\- ]{2,30}?(,| und | oder |$)", " ", kw)
    kw = re.sub(r"(welche[rs]?|mit|mit einem|der|die|das|ein(?:e|er|em)?|und|oder|zum|für|to|with|a|an|the|that|uses?|use|which|charge[sd]?|plug|to)\b", " ", kw)
    kw = re.sub(r"\s+", " ", kw).strip()
    return {"keywords": kw or tl[:80], "category": "", "hard": hard, "blacklist": blacklist,
            "whitelist": [], "attributes": attrs, "risk": {}, "enrich": True, "limit": 20}


async def stage_b_via_cloud(title: str, description: str, price: float | None,
                            keywords: str) -> dict[str, float]:
    out = await cloud_json(
        "You assess a marketplace listing. Return ONLY JSON: "
        "{exact (0..1: is it the requested product, not accessory/parts), "
        " risk (0..1 scam-risk), condition (0..1), note (one line why)}.",
        f"Looking for: {keywords}\nTitle: {title}\nPrice: {price}\nDescription: {(description or '')[:1500]}")
    if not out:
        return {}
    try:
        return {"exact": float(out.get("exact", 0.5)), "risk_ai": float(out.get("risk", 0.5)),
                "condition_ai": float(out.get("condition", 0.5)), "note": str(out.get("note", ""))[:200]}
    except (ValueError, TypeError):
        return {}


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

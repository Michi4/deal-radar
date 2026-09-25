"""Decision cascade: cheap heuristic (Stage A, every listing) -> Jev/Kev/LLM (Stage B, borderline only).

SystemOne interface matches TypeSafe Jev API shape:
  state: dict/str, questions: {id: {type: noul|choice|score, instructions, criteria}}
so Jev (hosted), Kev (self-hosted, Apache-2.0) and heuristics are interchangeable.
"""
from __future__ import annotations

import os
import re
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
    "liquid/lfm-2.5-2.6b:free,nvidia/nemotron-3.5-lightning:free,"
    "thinkingmachines/inkling-small:free,poolside/laguna-xs-2.1:free,"
    "qwen/qwen3.8-27b:free,google/gemma-4-31b-it:free,dots-studio/dots-3-note-preview:free,"
    "google/gemma-4-26b-a4b-it:free,z-ai/glm-5.2:free").split(",") if m.strip()]
if CLOUD_MODEL and CLOUD_MODEL not in CLOUD_MODELS:
    CLOUD_MODELS.insert(0, CLOUD_MODEL)


CLOUD_MODEL_VISION = os.getenv("CLOUD_MODEL_VISION", "qwen/qwen3.8-27b:free")  # free vision-language


async def _post_chat(base: str, key: str, model: str, system: str, user: str,
                   max_tokens: int, timeout: float = 60.0, raw: bool = False) -> dict | None:
    import json as _json
    try:
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        body: dict = {"model": model,
                      "messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": user}],
                      "temperature": 0.2, "max_tokens": max_tokens,
                      "think": False,  # ollama: skip chain-of-thought, answer directly
                      "options": {"num_predict": max_tokens}}
        if not raw:
            body["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(f"{base.rstrip('/')}/chat/completions", headers=headers, json=body)
            if r.status_code == 429:
                return {"__rate_limited": True}
            r.raise_for_status()
            msg = r.json()["choices"][0]["message"]
            content = (msg.get("content") or "").strip()
            if content:
                try:
                    return _json.loads(content)
                except Exception:
                    pass
            # small local models sometimes put JSON in `reasoning` with empty content
            blob = f"{msg.get('reasoning', '')}\n{content}"
            m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", blob, re.DOTALL) or re.search(r"(\{.*\})", blob, re.DOTALL)
            if m:
                try:
                    return _json.loads(m.group(1))
                except Exception:
                    pass
            return {"__error": f"no JSON in response: {blob[:120]}"}
    except Exception as e:
        return {"__error": str(e)[:150]}


_cloud_failures = 0
_cloud_disabled_until = 0.0


async def cloud_json(system: str, user: str, max_tokens: int = 600, model: str = "") -> dict | None:
    """Local-first (Ollama on laptop, free, private) then OpenRouter free-model failover.
    None when everything fails (offline-first deterministic fallback)."""
    global _cloud_failures, _cloud_disabled_until
    import asyncio as _aio
    import time as _t
    # 1) local backend (ollama OpenAI-compatible, no key needed)
    local_base = os.getenv("LOCAL_API_URL", "")
    local_model = os.getenv("LOCAL_MODEL", "qwen2.5:3b")
    if local_base and _t.time() >= _cloud_disabled_until:
        out = await _post_chat(local_base, "", local_model, system, user, max_tokens, timeout=30.0)
        if out and not out.get("__error") and not out.get("__rate_limited"):
            _cloud_failures = 0
            return out
        _cloud_failures += 1
        if _cloud_failures >= 3:
            _cloud_disabled_until = _t.time() + 600
            _cloud_failures = 0
    # 2) OpenRouter free failover with one retry round
    if not (CLOUD_API_URL and CLOUD_API_KEY):
        return None
    models = [model] if model else list(CLOUD_MODELS)
    last_err: str = ""
    for round_no in range(2):
        for m in models:
            out = await _post_chat(CLOUD_API_URL, CLOUD_API_KEY, m, system, user, max_tokens)
            if out is None:
                continue
            if out.get("__rate_limited"):
                last_err = f"{m}: 429"
                continue
            if out.get("__error"):
                last_err = f"{m}: {out['__error']}"
                continue
            return out
        if round_no == 0:
            await _aio.sleep(8)  # free-tier congestion is transient; one breather then retry
    print(f"[cloud] all models failed ({last_err})", flush=True)
    return None


async def cloud_code(system: str, user: str, max_tokens: int = 2000) -> str | None:
    """Raw code text: local Ollama first, then OpenRouter failover models. None when all fail."""
    import asyncio as _aio

    async def _raw(base: str, key: str, model: str) -> str | None:
        try:
            headers = {"Content-Type": "application/json"}
            if key:
                headers["Authorization"] = f"Bearer {key}"
            async with httpx.AsyncClient(timeout=180.0) as c:
                r = await c.post(f"{base.rstrip('/')}/chat/completions", headers=headers,
                                 json={"model": model,
                                       "messages": [{"role": "system", "content": system},
                                                    {"role": "user", "content": user}],
                                       "temperature": 0.2, "max_tokens": max_tokens, "think": False,
                                       "options": {"num_predict": max_tokens}})
                if r.status_code == 429:
                    return None
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"] or None
        except Exception:
            return None

    local_base = os.getenv("LOCAL_API_URL", "")
    if local_base:
        code = await _raw(local_base, "", os.getenv("LOCAL_MODEL", "qwen2.5:3b"))
        if code:
            return code
    if CLOUD_API_URL and CLOUD_API_KEY:
        for m in list(CLOUD_MODELS):
            code = await _raw(CLOUD_API_URL, CLOUD_API_KEY, m)
            if code:
                return code
        await _aio.sleep(5)
        for m in list(CLOUD_MODELS):
            code = await _raw(CLOUD_API_URL, CLOUD_API_KEY, m)
            if code:
                return code
    return None


NL_SYSTEM = ("You convert a natural-language second-hand search into a JSON SearchIntent. "
             "Use your product knowledge: resolve to concrete models (e.g. 'iPhone with USB-C charging' "
             "-> models ['iPhone 15','iPhone 15 Plus','iPhone 15 Pro','iPhone 15 Pro Max','iPhone 16',"
             "'iPhone 16 Plus','iPhone 16 Pro','iPhone 16 Pro Max','iPhone 17','iPhone Air']; "
             "'ThinkPad with OLED' -> ThinkPad models known with OLED options). "
             "Return ONLY JSON with keys: keywords (broad marketplace search words), "
             "models [] (exact product models that qualify — listings must match one), "
             "exclude [] (words that disqualify: accessories like case/hülle/kabel/charger, wrong variants, "
             "other brands, 'defekt' if user wants working), "
             "category, hard {max_price, min_price, rules[]}, blacklist[] ({fields,op,value}), "
             "attributes {} (requirements like connector:usb-c), risk_note. "
             "Rules use {field,op,value} with op in contains,not_contains,regex,lt,gt,range,equals. "
             "Never invent prices. Missing info -> omit the key.")


_NL_CACHE = "data/nl_cache.json"


def _nl_key(text: str) -> str:
    import hashlib as _h
    return _h.sha256((NL_SYSTEM + "\n" + text.strip().lower()).encode()).hexdigest()[:32]


def _nl_cached(text: str) -> dict | None:
    import json as _json
    import time as _t
    from pathlib import Path as _P
    try:
        p = _P(_NL_CACHE)
        if p.exists():
            key = _nl_key(text)
            d = _json.loads(p.read_text())
            if key in d and _t.time() - d[key].get("ts", 0) < 7 * 86400:
                return d[key]["intent"]
    except Exception:
        pass
    return None


def _nl_store(text: str, intent: dict) -> None:
    import json as _json
    import time as _t
    from pathlib import Path as _P
    try:
        p = _P(_NL_CACHE)
        d = _json.loads(p.read_text()) if p.exists() else {}
        key = _nl_key(text)
        d[key] = {"ts": _t.time(), "intent": intent}
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_json.dumps(d))
    except Exception:
        pass


async def nl_to_intent(text: str) -> dict:
    """Natural language -> SearchIntent. Cloud model when configured, deterministic fallback otherwise."""
    hit = _nl_cached(text)
    if hit:
        return hit
    cloud = await cloud_json(NL_SYSTEM, text)
    if cloud and isinstance(cloud.get("keywords"), str):
        bl = cloud.get("blacklist", []) or []
        for ex in (cloud.get("exclude", []) or []):
            bl.append({"fields": ["title", "description", "tags"], "op": "not_contains", "value": str(ex)})
        models = cloud.get("models", []) or []
        # guard: never exclude words that are part of the product itself (e.g. 'Apple' for iPhones)
        import re as _re2
        keep = _re2.sub(r"[^a-z0-9]+", "", cloud["keywords"].lower())
        modelblob = _re2.sub(r"[^a-z0-9]+", "", " ".join(models).lower())
        def _selfterm(v: str) -> bool:
            n = _re2.sub(r"[^a-z0-9]+", "", v.lower())
            return bool(n) and (n in keep or n in modelblob)
        bl = [b for b in bl if not _selfterm(str(b.get("value", "")))]
        # follow-up: model skipped model resolution but query implies specific models
        import re as _re3
        if not models and (any(w in text.lower() for w in
                               ("which", "with", "mit", "welche", "ohne", "that", "uses", "having", "haben"))
                           or _re3.search(r"\d", text)):  # model numbers ("845 g8", "iphone 15") = specific product
            fix = await cloud_json(
                "You know every product lineup. Return ONLY JSON {models: [exact model names], "
                "exclude: [accessory/wrong-variant words]}.",
                f"Query: {text}\nKeywords so far: {cloud['keywords']}\n"
                "List ONLY the exact product models that satisfy the query "
                "(e.g. USB-C iPhones -> iPhone 15 and newer, no cases/cables/chargers/Android).")
            if fix:
                models = fix.get("models", []) or []
                for ex in (fix.get("exclude", []) or []):
                    bl.append({"fields": ["title", "description", "tags"],
                               "op": "not_contains", "value": str(ex)})
        # final guard (after follow-up): never exclude words that are part of the product itself
        modelblob = _re2.sub(r"[^a-z0-9]+", "", " ".join(models).lower())
        makers = {"apple", "samsung", "lenovo", "xiaomi", "sony", "google", "huawei", "oneplus",
                  "dell", "hp", "asus", "acer", "msi", "nokia", "motorola", "nothing", "fairphone"}
        def _maker(v: str) -> bool:
            return _re2.sub(r"[^a-z0-9]+", "", v.lower()) in makers
        bl = [b for b in bl if not (_selfterm(str(b.get("value", ""))) or _maker(str(b.get("value", ""))))]
        intent = {"keywords": cloud["keywords"], "category": cloud.get("category", ""),
                  "hard": cloud.get("hard", {}) if isinstance(cloud.get("hard"), dict) else {"rules": cloud.get("hard", [])},
                  "blacklist": bl,
                  "whitelist": [], "attributes": cloud.get("attributes", {}),
                  "models": models,
                  "risk": {}, "enrich": True, "limit": 20}
        _nl_store(text, intent)
        return intent
    fb = nl_fallback(text)
    fb["models"] = []
    return fb


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
        res: dict[str, object] = {"exact": float(out.get("exact", 0.5)), "risk_ai": float(out.get("risk", 0.5)),
                                  "condition_ai": float(out.get("condition", 0.5)),
                                  "note": str(out.get("note", ""))[:200]}
        return res  # type: ignore[return-value]
    except (ValueError, TypeError):
        return {}


def heuristic_decide(title: str, description: str, price: float | None,
                     keywords: str) -> dict[str, Any]:
    """Stage A: deterministic, offline, ~µs. Returns match 0..1 + flags."""
    from rapidfuzz import fuzz
    kw = [k for k in keywords.lower().split() if k]
    hay = f"{title}\n{description}".lower()
    import re as _re
    hay_words = set(_re.findall(r"[a-z0-9]+", hay))
    if not kw:
        token_score = 0.5
    else:
        # whole-word hits; short tokens (hp, g8) only as words, longer ones may substring-match
        hits = sum(1 for k in kw if k in hay_words or (len(k) >= 4 and k in hay))
        token_score = hits / max(1, len(kw))
    fuzzy = fuzz.token_set_ratio(keywords.lower(), f"{title}".lower()) / 100.0 if keywords else 0.5
    match = round(0.7 * token_score + 0.3 * fuzzy, 3)
    import re as _re
    # buy-request / parts / repair ads are not buyable offers — penalty, evidence-logged
    want_ad = bool(_re.search(r"^\s*(ankauf|suche|gesuch|tausch\w*)\b|[\s(](gesucht|ankauf|tausch\w*)\b", hay))
    parts_ad = bool(_re.search(r"\b(backcover|r[üu]ckglas|r[üu]ckseite|ersatzteil|defekt|bastler|reparatur|reparieren|displaytausch|nur teile|f[üu]r teile|wasserschaden|icloud|frp)\b", hay))
    accessory_ad = bool(_re.search(r"\b(h[üu]lle(n)?|case(s)?|cover(s)?|schutzh[üu]lle|folie(n)?|panzerglas|leere?\s*(ovp|box)|ovp\s*leer|empty\s*box|box|schachtel|nur\s*(ovp|verpackung)|verpackung|karton|bumper|g[üu]rtelclip|armband|ladekabel|ladeger[äa]t|netzteil|halterung|st[äa]nder|dock|rucksack|tasche|laptoptasche|notebooktasche|sleeve|m[äa]ppchen|etui|beutel|umh[äa]ngetasche|vertrag|tarif|allnet|monatlich|abo|gewinnspiel|verlosung|gagner|tariff)\b", hay))
    if want_ad:
        match = round(match * 0.3, 3)
    elif parts_ad or accessory_ad:
        match = round(match * 0.5, 3)
    # kind caps: non-offers can never outrank real offers, no matter the keyword hits
    if want_ad:
        match = min(match, 0.30)
    elif parts_ad:
        match = min(match, 0.55)
    elif accessory_ad:
        match = min(match, 0.45)
    low_info = len(description or "") < 40
    kind = "want" if want_ad else ("parts" if parts_ad else ("accessory" if accessory_ad else "offer"))
    # condition from text signals (replaces placeholder 0.5)
    cond = 0.65
    if _re.search(r"\b(neu|neuwertig|ovp|originalverpackt|top|einwandfrei|makellos|kaum benutzt)\b", hay):
        cond = 0.9
    if _re.search(r"\b(sehr gut|gut erhalten|gepflegt|voll funktionsf[äa]hig)\b", hay):
        cond = max(cond, 0.78)
    if _re.search(r"\b(gebrauchsspuren|normale spuren|b-stock|b-ware)\b", hay):
        cond = min(cond, 0.55)
    if _re.search(r"\b(defekt|kaputt|gesprungen|risse?|kratzer|fehler|reparatur|bastler|f[üu]r teile)\b", hay):
        cond = 0.25
    return {"match": match, "fuzzy": round(fuzzy, 3), "low_info": low_info,
            "want_ad": want_ad or accessory_ad, "parts_ad": parts_ad, "kind": kind,
            "condition": round(cond, 2),
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

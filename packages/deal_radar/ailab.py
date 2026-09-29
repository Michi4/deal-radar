"""AI Lab: generate enrichers/drivers from chat, contract-check, hot-load, publish.

Authoring contract lives in docs/DRIVER_AUTHORING.md (coding agents: read it first —
it defines the driver/enricher interfaces, the category convention, the pagination
contract with cooperative stop/pause, and the evidence rules).

POST /lab/build {kind: "enricher"|"driver", instruction: "...", publish: false}
Flow: cloud/local model writes code -> syntax+contract check -> saved to
enrichers/custom/<id>.py or drivers/community/<id>/ -> hot-loaded without restart.
publish=true opens a GitHub PR against the repo (needs GH_TOKEN + LAB_PUBLISH=1).
Gated by LAB_ENABLED=1 (off by default — this writes runnable code).
"""
from __future__ import annotations

import ast
import os
import re
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
# Lab outputs live on the persisted volume (/data) so they survive rebuilds.
LAB_DIR = Path(os.getenv("LAB_DIR", str(ROOT / "enrichers" / "custom")))
LAB_DRIVERS = Path(os.getenv("LAB_DRIVERS", str(ROOT / "drivers" / "community")))

ENRICHER_PROMPT = """You write a deal-radar enricher plugin (Python, no new dependencies beyond httpx/pydantic).
(Read docs/DRIVER_AUTHORING.md first if available — it is the contract.)
Contract (exact — listing is a CanonicalListing OBJECT with attribute access, NOT a dict):
from deal_radar.enrich import Enricher, register
from deal_radar.contracts import EnrichmentFact, FactStatus, Evidence
class <Name>Enricher(Enricher):
    id = "<id>"; version = "0.1.0"
    def supports(self, listing) -> bool: return <True or a cheap field check>
    def enrich(self, listing, ctx):
        title = listing.title or ""; desc = listing.description or ""
        ... return [EnrichmentFact(field="<field>", value=<v>, confidence=<0..1>,
            status=FactStatus.EXTERNAL, sources=[Evidence(type="external", detail="<src>")])]
register(<Name>Enricher())
Rules: attribute access ONLY (listing.title, listing.description, listing.price, listing.images);
never raise (catch everything, return [] on failure); polite HTTP (<=1 req/s, 15s timeout,
browser UA); evidence in every fact; no API keys (none available).
TASK: {instruction}
Return ONLY the Python code, no markdown fences."""

DRIVER_PROMPT = """You write a deal-radar marketplace driver (Python, deps: httpx, pydantic only).
(Read docs/DRIVER_AUTHORING.md first if available — interfaces, categories, pagination + stop/pause contract.)
Contract (exact):
from deal_radar.driver_sdk import MarketplaceDriver, DriverManifest, SearchQuery
from deal_radar.contracts import CanonicalListing, Seller
class <Name>Driver(MarketplaceDriver):
    manifest = DriverManifest(id="<id>", version="0.1.0", display_name="<Name>",
        regions=[...], capabilities=["search"], access_mode="public_web", automation_permission="unknown")
    async def search(self, query: SearchQuery) -> list[CanonicalListing]:
        ... fetch search page, parse cards, return CanonicalListing list ...
Rules: missing fields -> ""/None/[] (never raise on missing data); 403/empty -> raise RuntimeError
with clear cause; <=1 req/s; browser User-Agent.
SITE/TASK: {instruction}
Return ONLY the Python code, no markdown fences."""


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:32] or f"custom-{int(time.time()) % 10000}"


REFINE_TMPL = """You previously wrote this code for the task below. The user has follow-up
instructions and/or the last version failed its checks with the error shown.
Return the FULL corrected Python file (raw code only, no markdown fences).

ORIGINAL TASK: {instruction}
PREVIOUS CODE:
```
{code}
```
LAST RESULT: {error}
FOLLOW-UP: {followup}"""

STAGES = ["prompting", "waiting_model", "validating", "saving", "contract_check", "done"]


async def generate(kind: str, instruction: str, followup: str = "",
                   prior_code: str = "", prior_error: str = "",
                   progress=None) -> dict:
    """Staged build with user follow-ups. progress(stage, msg) called throughout."""
    from deal_radar.decision import cloud_code
    if kind not in ("enricher", "driver"):
        return {"ok": False, "error": "kind must be enricher|driver"}
    prompt = ENRICHER_PROMPT if kind == "enricher" else DRIVER_PROMPT
    if prior_code or followup:
        task = REFINE_TMPL.format(instruction=instruction, code=prior_code[:6000],
                                  error=prior_error[:1000] or "n/a",
                                  followup=followup or instruction)
    else:
        task = prompt.format(instruction=instruction)
    if progress:
        progress("prompting", f"task packaged ({len(task)} chars)")
        progress("waiting_model", "asking model for code…")
    code = await cloud_code("You output raw Python code only. No markdown, no explanation.", task)
    if not code:
        return {"ok": False, "error": "no model available (local + cloud unreachable)"}
    import re as _re
    m = _re.search(r"```(?:python)?\s*(.*?)```", code, _re.DOTALL)
    code = (m.group(1) if m else code).strip()
    if progress:
        progress("validating", f"syntax + import gate on {len(code)} chars…")
    err = validate_python(code)
    if err:
        return {"ok": False, "error": err, "code": code[:2000]}
    eid = _slug((followup or instruction)[:40])
    if progress:
        progress("saving", f"saving {kind} {eid}…")
    path = save_enricher(code, eid) if kind == "enricher" else save_driver(code, eid)
    if progress:
        progress("contract_check", "hot-loading + firing on samples…")
    checks: dict = {}
    if kind == "enricher":
        if progress:
            progress("contract_check", "sandbox fire-check (no secrets, net allowlist, limits)…")
        from deal_radar.lab_sandbox import run_in_sandbox
        samples = [{"title": "TEST WARRANTY Garantie 12 Monate",
                    "description": "volle Gewaehrleistung"},
                   {"title": "plain thing", "description": "nothing special here"}]
        sb = run_in_sandbox(str(path), samples)
        if not sb.get("ok"):
            checks = {"ok": False,
                      "error": "sandbox refused: " + str(sb.get("error") or sb.get("errors") or "unknown")}
        else:
            checks = hotload_enricher(path)
            checks["sandbox"] = {"fired": sb.get("fired"), "net_blocked": sb.get("net_blocked", 0)}
            if checks.get("ok") and checks.get("supported_sample") and not checks.get("fired_on_sample"):
                checks = {"ok": False,
                          "error": "contract check: enricher claims support on samples but returns "
                                   "nothing (fix patterns or contract shapes: EnrichmentFact(field, "
                                   "value, confidence, status; Evidence(type, detail)))",
                          "sandbox": checks.get("sandbox")}
    else:
        from deal_radar.registry import check as _check
        checks = _check(path.parent.name)
    result: dict[str, Any] = {"ok": bool(checks.get("ok")), "kind": kind,
                                 "id": path.parent.name if kind == "driver" else path.stem,
                                 "path": str(path), "checks": checks}
    if not result["ok"]:
        result["error"] = checks.get("error", "contract check failed")
        result["code"] = code[:3000]
    if progress:
        progress("done", "ok — live" if result["ok"] else f"failed: {result.get('error', '')[:120]}")
    return result


_IMPORT_ALLOW = {"deal_radar", "re", "math", "statistics", "datetime", "json",
                  "unicodedata", "functools", "itertools",
                  "httpx", "pydantic", "asyncio", "time", "urllib"}
_CALL_DENY = {"eval", "exec", "open", "__import__", "compile", "input", "breakpoint"}
_ATTR_DENY = {"__subclasses__", "__bases__", "__mro__", "__globals__", "__code__",
              "__closure__", "__dict__", "__weakref__", "gi_frame", "f_globals"}


def validate_python(code: str) -> str | None:
    """Syntax + import/call AST gate (import-time surface). Execution behavior is proven
    separately in the lab_sandbox subprocess (no secrets, net allowlist, rlimits) before
    any in-process hot-load — keep LAB behind auth regardless."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"syntax: {e}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                if n.name.split(".")[0] not in _IMPORT_ALLOW:
                    return f"import not allowed: {n.name}"
        elif isinstance(node, ast.ImportFrom):
            if (node.level or 0) > 0:
                return "relative imports not allowed"
            if (node.module or "").split(".")[0] not in _IMPORT_ALLOW:
                return f"import not allowed: {node.module}"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _CALL_DENY:
            return f"call not allowed: {node.func.id}"
        elif isinstance(node, ast.Attribute) and node.attr in _ATTR_DENY:
            return f"attribute not allowed: {node.attr}"
    return None


def save_enricher(code: str, eid: str) -> Path:
    LAB_DIR.mkdir(parents=True, exist_ok=True)
    p = LAB_DIR / f"{eid}.py"
    p.write_text(code)
    return p


def save_driver(code: str, did: str) -> Path:
    d = LAB_DRIVERS / did
    d.mkdir(parents=True, exist_ok=True)
    p = d / "driver.py"
    p.write_text(code)
    return p


def load_custom_enrichers() -> list[str]:
    """Hot-load all persisted lab enrichers (called at startup)."""
    loaded: list[str] = []
    for p in sorted(LAB_DIR.glob("*.py")) if LAB_DIR.exists() else []:
        try:
            r = hotload_enricher(p)
            if r.get("ok"):
                loaded.append(p.stem)
        except Exception:
            continue
    return loaded


def hotload_enricher(path: Path) -> dict:
    import importlib.util
    try:
        spec = importlib.util.spec_from_file_location(f"lab_{path.stem}", path)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        from deal_radar.enrich import REGISTRY as _REG
        _before = {k: id(v) for k, v in _REG.items()}
        spec.loader.exec_module(mod)
        # live fire-check: run the NEWLY registered enricher(s) against samples
        from deal_radar.contracts import CanonicalListing, Seller
        from deal_radar.enrich import REGISTRY
        mk = lambda t, d: CanonicalListing(id="labtest", source="lab", native_id="x", url="u",
                                           title=t, description=d, price=1.0, seller=Seller(name="s"))
        _candidates = [eid for eid, enr in REGISTRY.items()
                       if eid not in _before or id(enr) != _before[eid]]
        fired = False
        supported = False
        for eid in _candidates:
            enr = REGISTRY[eid]
            try:
                for _t, _d in (("TEST WARRANTY Garantie 12 Monate", "volle Gewaehrleistung"),
                               ("plain thing", "nothing special here")):
                    _m = mk(_t, _d)
                    try:
                        if enr.supports(_m):
                            supported = True
                            if enr.enrich(_m, {}):
                                fired = True
                    except Exception:
                        pass
                r1 = enr.enrich(mk("TEST WARRANTY Garantie 12 Monate", "volle Gewaehrleistung"), {})
                enr.enrich(mk("plain thing", "nothing special here"), {})
                if r1:
                    fired = True
            except Exception as e:
                return {"ok": False, "error": f"enrich() raised on sample: {e}"}
        return {"ok": True, "enrichers": sorted(REGISTRY.keys()), "fired_on_sample": fired,
                "supported_sample": supported}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

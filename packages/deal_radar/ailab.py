"""AI Lab: generate enrichers/drivers from chat, contract-check, hot-load, publish.

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

ROOT = Path(__file__).resolve().parents[2]
# Lab outputs live on the persisted volume (/data) so they survive rebuilds.
LAB_DIR = Path(os.getenv("LAB_DIR", str(ROOT / "enrichers" / "custom")))
LAB_DRIVERS = Path(os.getenv("LAB_DRIVERS", str(ROOT / "drivers" / "community")))

ENRICHER_PROMPT = """You write a deal-radar enricher plugin (Python, no new dependencies beyond httpx/pydantic).
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


async def generate(kind: str, instruction: str) -> dict:
    from deal_radar.decision import cloud_code
    if kind not in ("enricher", "driver"):
        return {"ok": False, "error": "kind must be enricher|driver"}
    prompt = ENRICHER_PROMPT if kind == "enricher" else DRIVER_PROMPT
    code = await cloud_code("You output raw Python code only. No markdown, no explanation.",
                            prompt.format(instruction=instruction))
    if not code:
        return {"ok": False, "error": "no model available (local + cloud unreachable)"}
    import re as _re
    m = _re.search(r"```(?:python)?\s*(.*?)```", code, _re.DOTALL)
    code = (m.group(1) if m else code).strip()
    err = validate_python(code)
    if err:
        return {"ok": False, "error": err, "code": code[:2000]}
    eid = _slug(instruction[:40])
    path = save_enricher(code, eid) if kind == "enricher" else save_driver(code, eid)
    checks: dict = {}
    if kind == "enricher":
        checks = hotload_enricher(path)
    else:
        from deal_radar.registry import check as _check
        checks = _check(path.parent.name)
    result = {"ok": bool(checks.get("ok")), "kind": kind, "id": path.parent.name if kind == "driver" else path.stem,
              "path": str(path), "checks": checks}
    if not result["ok"]:
        result["code"] = code[:3000]
    return result


def validate_python(code: str) -> str | None:
    try:
        ast.parse(code)
        return None
    except SyntaxError as e:
        return f"syntax: {e}"


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
        spec.loader.exec_module(mod)
        from deal_radar.enrich import REGISTRY
        # live fire-check: run enrich() against a matching + non-matching sample listing
        from deal_radar.contracts import CanonicalListing, Seller
        mk = lambda t, d: CanonicalListing(id="labtest", source="lab", native_id="x", url="u",
                                           title=t, description=d, price=1.0, seller=Seller(name="s"))
        fired = False
        for eid, enr in REGISTRY.items():
            if path.stem.replace("-", "_") in eid or eid in path.stem.replace("-", "_"):
                try:
                    r1 = enr.enrich(mk("TEST WARRANTY Garantie 12 Monate", "volle Gewaehrleistung"), {})
                    r2 = enr.enrich(mk("plain thing", "nothing special here"), {})
                    fired = bool(r1)
                except Exception as e:
                    return {"ok": False, "error": f"enrich() raised on sample: {e}"}
        return {"ok": True, "enrichers": sorted(REGISTRY.keys()), "fired_on_sample": fired}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

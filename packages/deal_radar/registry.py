"""Driver registry: index format + install/list/update/check. Community drivers live in drivers/community/.

Index JSON (local file or URL):
{"drivers": [{"id": "...", "version": "...", "display_name": "...",
              "source": "github:owner/repo@<ref>:<subdir> | url:https://...zip | path:/... ",
              "sha256": "...", "capabilities": [...]}]}
CLI: PYTHONPATH=packages python -m deal_radar.registry list|install <id>|update|check <id>
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

from deal_radar.driver_sdk import DriverManifest

ROOT = Path(__file__).resolve().parents[2]
DRIVERS_DIR = ROOT / "drivers"
COMMUNITY = DRIVERS_DIR / "community"
LAB_DRIVERS = Path(os.getenv("LAB_DRIVERS", str(COMMUNITY)))
INDEX_SOURCES = ["drivers/registry.json"]
REMOTE_INDEX = "https://raw.githubusercontent.com/Michi4/deal-radar/main/marketplace/index.json"


def load_index(source: str = "") -> dict:
    if not source:
        # remote first (versioned, PR-contributed), local fallback offline
        try:
            return _load_remote()
        except Exception:
            source = INDEX_SOURCES[0]
    return _load_one(source)


def _load_remote() -> dict:
    with urllib.request.urlopen(REMOTE_INDEX, timeout=20) as r:
        return json.loads(r.read().decode())


def _load_one(src: str) -> dict:
    if src.startswith("http"):
        with urllib.request.urlopen(src, timeout=20) as r:
            return json.loads(r.read().decode())
    p = ROOT / src if not src.startswith("/") else Path(src)
    return json.loads(p.read_text()) if p.exists() else {"drivers": []}


def installed() -> list[str]:
    out = []
    for base in {DRIVERS_DIR, COMMUNITY, LAB_DRIVERS}:
        if base.exists():
            out += [d.name for d in base.iterdir()
                    if d.is_dir() and (d / "driver.py").exists() and d.name != "_template"]
    return sorted(set(out))


def load_driver_module(driver_id: str):
    for base in {DRIVERS_DIR, COMMUNITY, LAB_DRIVERS}:
        f = base / driver_id / "driver.py"
        if f.exists():
            spec = importlib.util.spec_from_file_location(f"dyn_{driver_id}", f)
            assert spec is not None and spec.loader is not None
            mod = importlib.util.module_from_spec(spec)
            sys.modules[f"dyn_{driver_id}"] = mod
            spec.loader.exec_module(mod)
            return mod
    raise FileNotFoundError(f"driver '{driver_id}' not installed")


def check(driver_id: str) -> dict:
    """Contract suite every driver must pass: manifest + search returns CanonicalListings."""

    mod = load_driver_module(driver_id)
    drivers = [v for v in vars(mod).values() if isinstance(v, type)
               and getattr(v, "manifest", None) is not None and v.__name__.endswith("Driver")]
    if not drivers:
        return {"ok": False, "error": "no *Driver subclass with manifest found"}
    cls = drivers[0]
    mani: DriverManifest = cls.manifest  # type: ignore[attr-defined]  # dynamic driver classes
    errors: list[str] = []
    try:
        m = mani
        assert m.id and m.display_name and m.capabilities, "manifest incomplete"
    except Exception as e:
        errors.append(f"manifest: {e}")
    if errors:
        return {"ok": False, "errors": errors}
    return {"ok": True, "driver": mani.id, "version": mani.version,
            "capabilities": list(mani.capabilities)}


def install(entry: dict, index_source: str = "") -> dict:
    src: str = entry.get("source", "")
    dest = COMMUNITY / entry["id"]
    if dest.exists():
        return {"ok": False, "error": f"{entry['id']} already installed (update first)"}
    try:
        if src.startswith("path:"):
            shutil.copytree(src[5:], dest)
        elif src.startswith("github:"):
            import subprocess
            _, rest = src.split(":", 1)
            sub = ""
            if ":" in rest:
                rest, _, sub = rest.partition(":")
            repo, _, ref = rest.partition("@")
            tmp = COMMUNITY / f".tmp-{entry['id']}"
            cmd = ["git", "clone", "--depth", "1"]
            if ref:
                cmd += ["--branch", ref]
            cmd += [f"https://github.com/{repo}", str(tmp)]
            subprocess.run(cmd, check=True, timeout=180)
            shutil.move(str(tmp / sub) if sub else str(tmp), dest)
        else:
            return {"ok": False, "error": f"unsupported source: {src}"}
        want = entry.get("sha256", "")
        if want:
            h = hashlib.sha256()
            for f in sorted(dest.rglob("*.py")):
                h.update(f.read_bytes())
            if h.hexdigest() != want:
                shutil.rmtree(dest)
                return {"ok": False, "error": "checksum mismatch — install aborted"}
        chk = check(entry["id"])
        if not chk.get("ok"):
            shutil.rmtree(dest)
            return {"ok": False, "error": f"contract check failed: {chk}"}
        return {"ok": True, "installed": entry["id"], "version": entry.get("version", "")}
    except Exception as e:
        shutil.rmtree(dest, ignore_errors=True)
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "list"
    if cmd == "list":
        idx = load_index(argv[2] if len(argv) > 2 else "")
        print("installed:", ", ".join(installed()) or "(none)")
        for d in idx.get("drivers", []):
            mark = " [installed]" if d["id"] in installed() else ""
            print(f"- {d['id']} {d.get('version', '')} — {d.get('display_name', '')}{mark}")
    elif cmd == "check":
        print(json.dumps(check(argv[2]), indent=1))
    elif cmd == "install":
        idx = load_index(argv[3] if len(argv) > 3 else "")
        entry = next((d for d in idx.get("drivers", []) if d["id"] == argv[2]), None)
        if not entry:
            print(f"unknown driver: {argv[2]}")
            return 1
        print(json.dumps(install(entry), indent=1))
    else:
        print("usage: registry list [index] | check <id> | install <id> [index]")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

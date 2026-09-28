"""Lab sandbox: fire generated enricher code in a locked-down subprocess.

Parent API: run_in_sandbox(path, samples, timeout_s, net_allow, mem_mb, cpu_s).
Child guarantees: scrubbed env (no secrets), RLIMIT_CPU/AS, socket egress allowlist,
JSON result on stdout. Import-time surface stays under ailab.validate_python's AST gate.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

CHILD = r"""
import json, sys, socket as _sock

path, samples_json, allow_json = sys.argv[1], sys.argv[2], sys.argv[3]
allow_names = set(json.loads(allow_json))
samples = json.loads(samples_json)

# fresh DNS resolution for allowlist (before the guard goes up)
allow_ips = set()
for _n in allow_names:
    try:
        for _i in _sock.getaddrinfo(_n, 443, type=_sock.SOCK_STREAM):
            allow_ips.add(_i[4][0])
    except Exception:
        pass

_blocked = {"n": 0}
_orig_connect = _sock.socket.connect
def _guarded_connect(self, address):
    host = address[0] if isinstance(address, tuple) else str(address)
    if host in allow_names or host in allow_ips:
        return _orig_connect(self, address)
    _blocked["n"] += 1
    raise OSError("egress blocked by lab sandbox: " + str(host))
_sock.socket.connect = _guarded_connect
_orig_create = _sock.create_connection
def _guarded_create(address, *a, **k):
    host = address[0] if isinstance(address, tuple) else str(address)
    if host in allow_names or host in allow_ips:
        return _orig_create(address, *a, **k)
    _blocked["n"] += 1
    raise OSError("egress blocked by lab sandbox: " + str(host))
_sock.create_connection = _guarded_create

try:
    import resource as _res
    _cpu = int(sys.argv[4]); _mem = int(sys.argv[5])
    _res.setrlimit(_res.RLIMIT_CPU, (_cpu, _cpu + 5))
    _res.setrlimit(_res.RLIMIT_AS, (_mem * 1024 * 1024, _mem * 1024 * 1024))
except Exception:
    pass

import importlib.util as _ilu
from deal_radar.enrich import REGISTRY as _REG0
_before = set(_REG0.keys())
_spec = _ilu.spec_from_file_location("lab_sandbox_mod", path)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

from deal_radar.contracts import CanonicalListing, Seller
from deal_radar.enrich import REGISTRY
_new = [e for e in REGISTRY if e not in _before]
fired, errors = False, []
for _s in samples:
    try:
        _l = CanonicalListing(id="labtest", source="lab", native_id="x", url="u",
                              title=_s.get("title", ""), description=_s.get("description", ""),
                              price=1.0, seller=Seller(name="s"))
        for _eid in _new:
            _r = REGISTRY[_eid].enrich(_l, {})
            if _r:
                fired = True
    except OSError as _e:
        if "lab sandbox" in str(_e):
            continue
        errors.append(str(_e)[:200])
    except Exception as _e:
        errors.append(str(_e)[:200])
print(json.dumps({"ok": not errors, "fired": fired,
                  "net_blocked": _blocked["n"], "errors": errors}))
"""

_SECRET_HINTS = ("TOKEN", "KEY", "SECRET", "PASSWORD", "CERT", "NOTIFIERS",
                 "TRANSPORTS", "GH_", "LOGIN", "API_KEY", "SIGNAL", "WEBHOOK", "NTFY")


def scrub_env() -> dict:
    clean = {}
    for k, v in os.environ.items():
        ku = k.upper()
        if any(h in ku for h in _SECRET_HINTS):
            continue
        clean[k] = v
    return clean


def run_in_sandbox(path: str, samples: list[dict], timeout_s: int = 120,
                   net_allow: list[str] | None = None,
                   mem_mb: int = 512, cpu_s: int = 60) -> dict:
    """Fire an enricher file on samples inside the sandbox. Never raises."""
    if net_allow is None:
        net_allow = ["www.cpubenchmark.net", "www.videocardbenchmark.net"]
    env = scrub_env()
    try:
        repo_packages = str(Path(__file__).resolve().parents[2] / "packages")
        drivers_dir = str(Path(__file__).resolve().parents[2] / "drivers")
        env["PYTHONPATH"] = repo_packages + os.pathsep + drivers_dir + os.pathsep + env.get("PYTHONPATH", "")
    except Exception:
        pass
    try:
        p = subprocess.run(
            [sys.executable, "-c", CHILD, str(path), json.dumps(samples),
             json.dumps(net_allow), str(cpu_s), str(mem_mb)],
            capture_output=True, text=True, timeout=timeout_s, env=env, check=False)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "sandbox limit: wall timeout exceeded", "fired": False}
    if p.returncode not in (0, -9) and "Traceback" in (p.stderr or ""):
        tail = (p.stderr or "").strip().splitlines()[-3:]
        return {"ok": False, "error": "sandbox crash: " + " | ".join(tail)[:300], "fired": False}
    if p.returncode != 0:
        if p.returncode == -24 or "CPU" in (p.stderr or "") or not (p.stdout or "").strip():
            return {"ok": False, "error": "sandbox limit: killed (CPU/memory/time)", "fired": False}
        return {"ok": False, "error": f"sandbox exit {p.returncode}: {(p.stderr or '')[:200]}",
                "fired": False}
    try:
        return json.loads((p.stdout or "").strip().splitlines()[-1])
    except Exception:
        return {"ok": False, "error": "sandbox bad output: " + (p.stdout or "")[:200], "fired": False}

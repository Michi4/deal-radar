"""In-memory metrics with Prometheus exposition. Full insight: drivers, AI, pipeline."""
from __future__ import annotations
import time
from collections import Counter, defaultdict

_counters: Counter[str] = Counter()
_lat_sum: defaultdict[str, float] = defaultdict(float)
_lat_n: Counter[str] = Counter()
_gauges: dict[str, float] = {}


def inc(name: str, n: int = 1) -> None:
    _counters[name] += n


def observe_latency(name: str, seconds: float) -> None:
    _lat_sum[name] += seconds
    _lat_n[name] += 1


def set_gauge(name: str, v: float) -> None:
    _gauges[name] = v


def snapshot() -> dict:
    out = {"counters": dict(_counters), "gauges": dict(_gauges), "latency_avg_ms": {}}
    for k, s in _lat_sum.items():
        n = _lat_n[k] or 1
        out["latency_avg_ms"][k] = round(s / n * 1000, 2)
    return out


def prometheus() -> str:
    lines: list[str] = []
    for k, v in _counters.items():
        lines.append(f"dealradar_{k} {v}")
    for k, v in _gauges.items():
        lines.append(f"dealradar_{k} {v}")
    for k, s in _lat_sum.items():
        n = _lat_n[k] or 1
        lines.append(f"dealradar_{k}_avg_ms {s / n * 1000:.2f}")
    lines.append(f"dealradar_uptime_s {time.time() - _START:.0f}")
    return "\n".join(lines) + "\n"


_START = time.time()

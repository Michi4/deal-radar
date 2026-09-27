"""Cooperative cancellation shared by orchestrator, API layer, and drivers.

Drivers check should_stop()/pause_gate() on every page so a stop lands within
seconds even on hundred-page walks. No imports here on purpose (cycle-free).
"""
from __future__ import annotations

import asyncio as _aio
import time as _t

_STOP: set[str] = set()
_PAUSE: set[str] = set()
_PAUSE_SINCE: dict[str, float] = {}
PAUSE_TTL_S = 6 * 3600


def should_stop(sid: str | None) -> bool:
    return bool(sid and sid in _STOP)


async def pause_gate(sid: str | None) -> bool:
    """True if caller should abort (stopped). Waits while paused, max PAUSE_TTL_S."""
    if sid and sid in _PAUSE and sid not in _PAUSE_SINCE:
        _PAUSE_SINCE[sid] = _t.time()
    while sid and sid in _PAUSE and sid not in _STOP:
        if _t.time() - _PAUSE_SINCE.get(sid, _t.time()) > PAUSE_TTL_S:
            _PAUSE.discard(sid)
            _STOP.add(sid)
            break
        await _aio.sleep(2)
    if sid:
        _PAUSE_SINCE.pop(sid, None)
    return bool(sid and sid in _STOP)


def disarm(sid: str | None) -> None:
    if not sid:
        return
    _STOP.discard(sid)
    _PAUSE.discard(sid)
    _PAUSE_SINCE.pop(sid, None)

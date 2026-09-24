"""Notifications: pluggable channels (log/ntfy/webhook). Live push goes via SSE in the API."""
from __future__ import annotations
from typing import Any
import httpx


class Notifier:
    async def send(self, title: str, body: str, extra: dict[str, Any] | None = None) -> bool:
        raise NotImplementedError


class LogNotifier(Notifier):
    async def send(self, title: str, body: str, extra: dict | None = None) -> bool:
        print(f"[notify] {title} :: {body}", flush=True)
        return True


class NtfyNotifier(Notifier):
    def __init__(self, topic_url: str):
        self.topic_url = topic_url

    async def send(self, title: str, body: str, extra: dict | None = None) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                await c.post(self.topic_url, content=body, headers={"Title": title[:120]})
            return True
        except Exception:
            return False


class WebhookNotifier(Notifier):
    def __init__(self, url: str):
        self.url = url

    async def send(self, title: str, body: str, extra: dict | None = None) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                await c.post(self.url, json={"title": title, "body": body, **(extra or {})})
            return True
        except Exception:
            return False


def notifier_from_env(env: dict[str, str]) -> Notifier:
    if env.get("NTFY_TOPIC_URL"):
        return NtfyNotifier(env["NTFY_TOPIC_URL"])
    if env.get("WEBHOOK_URL"):
        return WebhookNotifier(env["WEBHOOK_URL"])
    return LogNotifier()

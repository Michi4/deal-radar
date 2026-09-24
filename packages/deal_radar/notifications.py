"""Notifications: pluggable channels + fan-out. Configure via NOTIFIERS_JSON env:
[{"type":"signal"},{"type":"ntfy","topic_url":"..."},{"type":"telegram","bot_token":"...","chat_id":"..."},
 {"type":"email","smtp_host":"...","smtp_user":"...","smtp_pass":"...","to":"..."},
 {"type":"webhook","url":"..."},{"type":"log"}]
Back-compat: SIGNAL_API_URL/SIGNAL_NUMBER, NTFY_TOPIC_URL, WEBHOOK_URL single envs.
Live push to browsers goes via SSE /stream; these channels are for push alerts.
"""
from __future__ import annotations
import json
import os
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
                await c.post(self.topic_url, content=f"{title}\n{body}"[:4000],
                             headers={"Title": title[:120]})
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


class SignalNotifier(Notifier):
    """Self-hosted Signal via bbernhard/signal-cli-rest-api (POST /v2/send)."""

    def __init__(self, api_url: str, number: str, recipients: list[str] | None = None):
        self.api_url = api_url.rstrip("/")
        self.number = number
        self.recipients = recipients or [number]

    async def send(self, title: str, body: str, extra: dict | None = None) -> bool:
        try:
            msg = f"[{title}]\n{body}"[:4000]
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(f"{self.api_url}/v2/send",
                                 json={"number": self.number, "recipients": self.recipients,
                                       "message": msg})
                r.raise_for_status()
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[notify:signal] failed: {e}", flush=True)
            return False


class TelegramNotifier(Notifier):
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    async def send(self, title: str, body: str, extra: dict | None = None) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                                 json={"chat_id": self.chat_id,
                                       "text": f"*{title}*\n{body}"[:4000],
                                       "parse_mode": "Markdown"})
                r.raise_for_status()
            return True
        except Exception:
            return False


class EmailNotifier(Notifier):
    def __init__(self, smtp_host: str, smtp_user: str, smtp_pass: str, to: str,
                 smtp_port: int = 465, sender: str = ""):
        self.cfg = (smtp_host, smtp_port, smtp_user, smtp_pass, to, sender or smtp_user)

    async def send(self, title: str, body: str, extra: dict | None = None) -> bool:
        import smtplib
        from email.message import EmailMessage
        host, port, user, pw, to, sender = self.cfg
        try:
            msg = EmailMessage()
            msg["Subject"] = f"[deal-radar] {title}"[:200]
            msg["From"] = sender
            msg["To"] = to
            msg.set_content(body + (f"\n\n{extra.get('url', '')}" if extra and extra.get("url") else ""))
            with smtplib.SMTP_SSL(host, port, timeout=15) as s:
                s.login(user, pw)
                s.send_message(msg)
            return True
        except Exception as e:  # noqa: BLE001
            print(f"[notify:email] failed: {e}", flush=True)
            return False


class MultiNotifier(Notifier):
    """Fan-out to all configured channels. One channel failing never blocks others."""

    def __init__(self, notifiers: list[Notifier]):
        self.notifiers = notifiers

    async def send(self, title: str, body: str, extra: dict | None = None) -> bool:
        ok = True
        for n in self.notifiers:
            try:
                if not await n.send(title, body, extra):
                    ok = False
            except Exception:
                ok = False
        return ok


def _from_spec(spec: dict[str, Any], env: dict[str, str]) -> Notifier | None:
    t = spec.get("type", "log")
    if t == "log":
        return LogNotifier()
    if t == "ntfy" and (spec.get("topic_url") or env.get("NTFY_TOPIC_URL")):
        return NtfyNotifier(spec.get("topic_url") or env["NTFY_TOPIC_URL"])
    if t == "webhook" and (spec.get("url") or env.get("WEBHOOK_URL")):
        return WebhookNotifier(spec.get("url") or env["WEBHOOK_URL"])
    if t == "signal" and (spec.get("number") or env.get("SIGNAL_NUMBER")):
        return SignalNotifier(spec.get("api_url") or env.get("SIGNAL_API_URL", "http://localhost:8082"),
                              spec.get("number") or env["SIGNAL_NUMBER"],
                              spec.get("recipients"))
    if t == "telegram" and spec.get("bot_token") and spec.get("chat_id"):
        return TelegramNotifier(spec["bot_token"], spec["chat_id"])
    if t == "email" and spec.get("smtp_host"):
        return EmailNotifier(spec["smtp_host"], spec.get("smtp_user", ""), spec.get("smtp_pass", ""),
                             spec.get("to", ""), int(spec.get("smtp_port", 465)))
    return None


def notifier_from_env(env: dict[str, str]) -> Notifier:
    try:
        specs = json.loads(env.get("NOTIFIERS_JSON", ""))
        if isinstance(specs, list):
            ns = [n for s in specs if (n := _from_spec(s, env))]
            if ns:
                return MultiNotifier(ns)
    except Exception:
        pass
    # back-compat single-channel envs, all fan out together
    ns: list[Notifier] = []
    if env.get("SIGNAL_NUMBER"):
        ns.append(SignalNotifier(env.get("SIGNAL_API_URL", "http://localhost:8082"), env["SIGNAL_NUMBER"]))
    if env.get("NTFY_TOPIC_URL"):
        ns.append(NtfyNotifier(env["NTFY_TOPIC_URL"]))
    if env.get("WEBHOOK_URL"):
        ns.append(WebhookNotifier(env["WEBHOOK_URL"]))
    ns.append(LogNotifier())
    return MultiNotifier(ns) if len(ns) > 1 else ns[0]

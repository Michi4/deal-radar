import asyncio, uuid
from deal_radar.notifications import NtfyNotifier, WebhookNotifier, SignalNotifier

topic = f"https://ntfy.sh/dealradar-test-{uuid.uuid4().hex[:8]}"
print("ntfy:", asyncio.run(NtfyNotifier(topic).send("deal-radar test", "live channel check"))),
print("webhook:", asyncio.run(WebhookNotifier("https://httpbin.org/post").send("t", "b")))
print("signal-unlinked:", asyncio.run(SignalNotifier("http://10.8.1.2:8082", "+4367763177763").send("t", "b")))

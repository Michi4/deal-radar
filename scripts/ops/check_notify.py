import asyncio, uuid
from deal_radar.notifications import NtfyNotifier, WebhookNotifier, SignalNotifier

topic = f"https://ntfy.sh/dealradar-test-{uuid.uuid4().hex[:8]}"
print("ntfy:", asyncio.run(NtfyNotifier(topic).send("deal-radar test", "live channel check"))),
print("webhook:", asyncio.run(WebhookNotifier("https://httpbin.org/post").send("t", "b")))
print("signal-unlinked:", asyncio.run(SignalNotifier("http://10.9.9.2:8082", "+430000000000").send("t", "b")))

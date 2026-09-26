import asyncio
from deal_radar.notifications import SignalNotifier

n = SignalNotifier("http://10.8.1.2:8082", "+4367763177763")
print(asyncio.run(n.send("deal-radar", "Stack check: notifier → signal-api → phone. Second ping, ignore.")))

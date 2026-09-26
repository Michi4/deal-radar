import asyncio
from deal_radar.notifications import SignalNotifier

n = SignalNotifier("http://10.9.9.2:8082", "+430000000000")
print(asyncio.run(n.send("deal-radar", "Stack check: notifier → signal-api → phone. Second ping, ignore.")))

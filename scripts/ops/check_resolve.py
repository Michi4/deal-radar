import asyncio
from deal_radar.scoring import resolve_cpu_candidates, extract_cpu

print("seed:", asyncio.run(resolve_cpu_candidates("HP EliteBook 845 G8")))
print("extract:", extract_cpu("hp elitebook 845 g8 - amd ryzen 5 pro | 16 gb ram"))

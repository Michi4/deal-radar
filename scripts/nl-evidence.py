import asyncio, json, os
os.environ.pop("LOCAL_API_URL", None)
from deal_radar.decision import nl_to_intent

QUERIES = [
    "iPhone that charges with USB-C",
    "ThinkPad under 500 euro",
    "RTX 4080 or RTX 4070 Ti Super",
    "bike for commuting in Vienna",
    "Galaxy phone without a cracked screen",
    "cheap espresso machine with warranty",
    "MacBook with at least 16GB RAM",
    "used road bike, no racing, pickup in Graz",
    "small sofa, pet friendly, under 300",
    "camera lens Canon EF, no fungus",
]

async def main():
    for q in QUERIES:
        try:
            p = await nl_to_intent(q)
            print(json.dumps({"q": q, "keywords": p.get("keywords"),
                              "models": (p.get("models") or [])[:6],
                              "blacklist": [(b.get("value") if isinstance(b, dict) else b) for b in (p.get("blacklist") or [])][:6],
                              "required": [(b.get("value") if isinstance(b, dict) else b) for b in (p.get("required") or [])][:6],
                              "hard": p.get("hard", {})}, ensure_ascii=False), flush=True)
        except Exception as e:
            print(json.dumps({"q": q, "ERROR": str(e)[:150]}), flush=True)

asyncio.run(main())

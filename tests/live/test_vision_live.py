"""Live vision pair proof (ACCEPTANCE 3/22): image-match discrimination.

2026-09-30 via TokenHarbor mimo-v2.5:free through deal_radar.vision.vision_check:
match (ThinkPad photo + ThinkPad title) -> shows_item 1.0;
mismatch (same photo + Dyson title) -> shows_item 0.0 + sensible note.
"""
import pytest

pytestmark = pytest.mark.live

MATCH_IMG = "https://img.kleinanzeigen.de/api/v1/prod-ads/images/d1/d1c5f85b-dc40-4fbe-86ae-e2f85db4c063?rule=$_2.AUTO"


def test_vision_pair_live():
    import asyncio

    from deal_radar.vision import vision_check

    async def go():
        m = await vision_check(
            MATCH_IMG, "Lenovo Thinkpad T480s i7-8550U 16GB Full HD",
            "Thinkpad T480s in gutem Zustand mit Netzteil")
        w = await vision_check(
            MATCH_IMG, "Dyson V15 Staubsauger",
            "kabelloser Staubsauger mit viel Zubehör")
        return m, w

    m, w = asyncio.run(go())
    ms, ws = float(m.get("shows_item", 0.5)), float(w.get("shows_item", 0.5))
    assert ms >= 0.7, m
    assert ws <= 0.4, w
    assert ms - ws >= 0.4, (m, w)

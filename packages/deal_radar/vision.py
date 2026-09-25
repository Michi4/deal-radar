"""Vision worker: OCR listing images (tesseract) + download helper. Best-effort, cached, never raises.

OCR text flows into ocr_texts so filters, CPU extraction and risk signals see photo content
(spec stickers, BIOS screens, invoices). Vision consistency (does the photo show the
described item) needs a vision model — hook: VISION_URL (OpenAI-compatible) when configured.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import httpx

_ocr_cache: dict[str, str] = {}
_cache_dir = Path("/tmp/opencode/dealradar-ocr")


def _tesseract_ok() -> bool:
    return shutil.which("tesseract") is not None


def download_image(url: str, timeout: float = 12.0) -> bytes | None:
    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0",
                               "Accept": "image/*,*/*;q=0.8",
                               "Referer": "https://www.kleinanzeigen.de/"})
        r.raise_for_status()
        if len(r.content) > 8_000_000:
            return None
        return r.content
    except Exception:
        return None


def ocr_bytes(img: bytes, lang: str = "eng+deu") -> str:
    if not _tesseract_ok() or not img:
        return ""
    key = hashlib.sha256(img).hexdigest()[:32]
    if key in _ocr_cache:
        return _ocr_cache[key]
    try:
        _cache_dir.mkdir(parents=True, exist_ok=True)
        p = _cache_dir / f"{key}.img"
        p.write_bytes(img)
        out = subprocess.run(["tesseract", str(p), "stdout", "-l", lang],
                             capture_output=True, text=True, timeout=25, check=False)
        text = (out.stdout or "").strip()[:2000]
        _ocr_cache[key] = text
        return text
    except Exception:
        return ""


def ocr_listing_images(images: list[str], max_images: int = 1) -> list[str]:
    texts: list[str] = []
    for url in (images or [])[:max_images]:
        if url in _ocr_cache:
            if _ocr_cache[url]:
                texts.append(_ocr_cache[url])
            continue
        img = download_image(url)
        t = ocr_bytes(img) if img else ""
        _ocr_cache[url] = t
        if t:
            texts.append(t)
    return texts


_vision_failures = 0
_vision_disabled_until = 0.0


async def vision_check(image_url: str, title: str, description: str) -> dict:
    """Ask a vision-language model: does the photo show the described item?
    Local vision model first (free, private), then OpenRouter free VLM.
    Backend circuit breaker: 3 consecutive failures -> skip for 10 min (laptop asleep etc).
    Returns {shows_item 0..1, is_stock 0..1, visible_text, note}. {} when unavailable."""
    import os
    import time as _t
    if _t.time() < _vision_disabled_until:
        return {}
    api, key = os.getenv("CLOUD_API_URL", ""), os.getenv("CLOUD_API_KEY", "")
    vmodel = os.getenv("CLOUD_MODEL_VISION", "qwen/qwen3.8-27b:free")
    local_base, local_vl = os.getenv("LOCAL_VISION_API_URL", "") or os.getenv("LOCAL_API_URL", ""), os.getenv("LOCAL_MODEL_VISION", "")

    def _fail() -> dict:
        global _vision_failures, _vision_disabled_until
        _vision_failures += 1
        if _vision_failures >= 3:
            _vision_disabled_until = _t.time() + 600
            _vision_failures = 0
        return {}

    def _ok() -> None:
        global _vision_failures
        _vision_failures = 0
    prompt = ("Listing title: " + title[:300] +
              "\nDescription: " + (description or "")[:800] +
              "\nReturn ONLY JSON: {shows_item (0..1: photo shows THIS item), "
              "is_stock (0..1: looks like a stock/catalog photo), "
              "visible_text (any readable spec text), "
              "note (one short line)}.")
    payload = lambda model: {"model": model,
                             "messages": [{"role": "user", "content": [
                                 {"type": "text", "text": prompt},
                                 {"type": "image_url", "image_url": {"url": image_url}}]}],
                             "response_format": {"type": "json_object"},
                             "temperature": 0.1, "max_tokens": 400, "think": False}
    try:
        import httpx
        # 1) local (ollama needs base64 data URLs — it won't fetch remote URLs itself)
        if local_base and local_vl:
            try:
                img = download_image(image_url)
                if img:
                    import base64 as _b64
                    data_url = "data:image/jpeg;base64," + _b64.b64encode(img).decode()
                    body = payload(local_vl)
                    body["messages"][0]["content"][1] = {"type": "image_url",
                                                         "image_url": {"url": data_url}}
                    async with httpx.AsyncClient(timeout=30.0) as c:
                        r = await c.post(f"{local_base.rstrip('/')}/chat/completions", json=body)
                        r.raise_for_status()
                        _ok()
                        return _parse_vision(r.json())
                return _fail()
            except Exception:
                return _fail()
        # 2) cloud free VLM
        if not (api and key and image_url):
            return {}
        async with httpx.AsyncClient(timeout=45.0) as c:
            r = await c.post(f"{api.rstrip('/')}/chat/completions",
                             headers={"Authorization": f"Bearer {key}"}, json=payload(vmodel))
            if r.status_code == 429:
                return _fail()
            r.raise_for_status()
            _ok()
            return _parse_vision(r.json())
    except Exception:
        return _fail()


def _parse_vision(data: dict) -> dict:
    try:
        import json as _json
        import re as _re
        msg = data["choices"][0]["message"]
        content = (msg.get("content") or "").strip() or msg.get("reasoning", "")
        m = _re.search(r"(\{.*\})", content, _re.DOTALL)
        out = _json.loads(m.group(1)) if m else {}
        shows = float(out.get("shows_item", 0.5))
        note = str(out.get("note", ""))
        # small VLMs sometimes score high while describing a mismatch — trust the words
        if _re.search(r"not match|doesn.?t (show|match)|different (product|item)|wrong item|unrelated",
                      note, _re.IGNORECASE):
            shows = min(shows, 0.25)
        return {"shows_item": shows,
                "is_stock": float(out.get("is_stock", 0.5)),
                "visible_text": str(out.get("visible_text", ""))[:500],
                "note": note[:200]}
    except Exception:
        return {}

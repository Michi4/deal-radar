"""Vision worker: OCR listing images (tesseract) + download helper. Best-effort, cached, never raises.

OCR text flows into ocr_texts so filters, CPU extraction and risk signals see photo content
(spec stickers, BIOS screens, invoices). Vision consistency (does the photo show the
described item) needs a vision model — hook: VISION_URL (OpenAI-compatible) when configured.
"""
from __future__ import annotations
import hashlib
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
import httpx

_ocr_cache: dict[str, str] = {}
_cache_dir = Path("/tmp/opencode/dealradar-ocr")


def _tesseract_ok() -> bool:
    return shutil.which("tesseract") is not None


def download_image(url: str, timeout: float = 12.0) -> bytes | None:
    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0"})
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
                             capture_output=True, text=True, timeout=25)
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


async def vision_check(image_url: str, title: str, description: str) -> dict:
    """Ask a free vision-language model: does the photo show the described item?
    Returns {shows_item 0..1, is_stock 0..1, visible_text, note}. {} when unavailable."""
    import os
    api, key = os.getenv("CLOUD_API_URL", ""), os.getenv("CLOUD_API_KEY", "")
    vmodel = os.getenv("CLOUD_MODEL_VISION", "qwen/qwen3.8-27b:free")
    if not (api and key and image_url):
        return {}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.post(f"{api.rstrip('/')}/chat/completions",
                             headers={"Authorization": f"Bearer {key}"},
                             json={"model": vmodel,
                                   "messages": [{
                                       "role": "user",
                                       "content": [
                                           {"type": "text",
                                            "text": "Listing title: " + title[:300] +
                                                    "\nDescription: " + (description or "")[:800] +
                                                    "\nReturn ONLY JSON: {shows_item (0..1: photo shows THIS item), "
                                                    "is_stock (0..1: looks like a stock/catalog photo), "
                                                    "visible_text (any readable spec text), "
                                                    "note (one short line)}."},
                                           {"type": "image_url", "image_url": {"url": image_url}}]}],
                                   "response_format": {"type": "json_object"},
                                   "temperature": 0.1, "max_tokens": 400})
            if r.status_code == 429:
                return {}
            r.raise_for_status()
            import json as _json
            out = _json.loads(r.json()["choices"][0]["message"]["content"])
            return {"shows_item": float(out.get("shows_item", 0.5)),
                    "is_stock": float(out.get("is_stock", 0.5)),
                    "visible_text": str(out.get("visible_text", ""))[:500],
                    "note": str(out.get("note", ""))[:200]}
    except Exception:
        return {}

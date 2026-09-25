"""Cross-marketplace same-item detection via average perceptual hash (Pillow only).

Same physical item often appears on multiple platforms (resellers, cross-posting).
aHash (8x8) + hamming distance <= threshold => same item. Cached, best-effort, never raises.
"""
from __future__ import annotations

import io

from .vision import download_image

_hash_cache: dict[str, int | None] = {}


def ahash(img_bytes: bytes) -> int | None:
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(img_bytes)).convert("L").resize((8, 8), Image.Resampling.BILINEAR)
        getdata = getattr(im, "get_flattened_data", None) or im.getdata
        px = list(getdata())
        avg = sum(px) / len(px)
        h = 0
        for i, v in enumerate(px):
            if v > avg:
                h |= 1 << i
        return h
    except Exception:
        return None


def image_hash(url: str) -> int | None:
    if url in _hash_cache:
        return _hash_cache[url]
    img = download_image(url)
    h = ahash(img) if img else None
    _hash_cache[url] = h
    return h


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def find_dupes(hashes: dict[str, int | None], threshold: int = 6) -> list[tuple[str, str, int]]:
    ids = [(k, v) for k, v in hashes.items() if v is not None]
    out: list[tuple[str, str, int]] = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            d = hamming(ids[i][1], ids[j][1])
            if d <= threshold:
                out.append((ids[i][0], ids[j][0], d))
    return out

"""Shape-normalised glyph matcher.

The first attempt correlated raw 16x16 boxes and did badly, because the game's
glyphs sit in an ink box of roughly 15x14 while a rendered font fills the whole em
square — so every comparison was fighting a scale and offset mismatch.

Here both sides are cropped to their ink bounding box, fitted into a common square
while preserving aspect ratio, and lightly blurred so that a one-pixel difference in
stroke placement does not destroy the correlation.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import font as fontlib

STREAM = Path(r"D:\psp\원격수사\font_extract\script_stream.bin")
FONT_DIR = Path(r"C:\Windows\Fonts")
FONT_OFFSET = 0x80
FONT_TILES = 684

NORM = 32          # normalised comparison size
BLUR = 1.2
INK = 0.12         # ink threshold as a fraction of max


def normalise(image: np.ndarray) -> np.ndarray:
    """Crop to ink, fit into NORM x NORM keeping aspect, blur, zero-mean."""
    arr = image.astype(np.float32)
    peak = arr.max()
    if peak <= 0:
        return np.zeros((NORM, NORM), dtype=np.float32)
    mask = arr > peak * INK
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    if len(rows) == 0 or len(cols) == 0:
        return np.zeros((NORM, NORM), dtype=np.float32)
    crop = arr[rows[0] : rows[-1] + 1, cols[0] : cols[-1] + 1]
    crop = crop / peak * 255.0

    h, w = crop.shape
    scale = (NORM - 4) / max(h, w)
    new_h, new_w = max(1, round(h * scale)), max(1, round(w * scale))
    resized = Image.fromarray(crop.astype(np.uint8), "L").resize((new_w, new_h), Image.BILINEAR)

    canvas = Image.new("L", (NORM, NORM), 0)
    canvas.paste(resized, ((NORM - new_w) // 2, (NORM - new_h) // 2))
    canvas = canvas.filter(ImageFilter.GaussianBlur(BLUR))
    out = np.asarray(canvas, dtype=np.float32)
    out -= out.mean()
    norm = np.linalg.norm(out)
    return out / norm if norm else out


def game_glyphs() -> np.ndarray:
    raw = fontlib.tiles_to_glyphs(STREAM.read_bytes(), FONT_OFFSET, FONT_TILES)
    return np.stack([normalise(g) for g in raw])


def cp932_candidates() -> list[str]:
    chars, seen = [], set()
    for lead in range(0x81, 0xF0):
        for trail in range(0x40, 0xFD):
            if trail == 0x7F:
                continue
            try:
                ch = bytes([lead, trail]).decode("cp932")
            except UnicodeDecodeError:
                continue
            if len(ch) == 1 and ch not in seen:
                seen.add(ch)
                chars.append(ch)
    return chars


def render_normalised(chars: list[str], font_file: str, face: int, px: int = 64) -> np.ndarray:
    pil_font = ImageFont.truetype(str(FONT_DIR / font_file), px, index=face)
    box = px * 2
    canvas = Image.new("L", (box, box))
    draw = ImageDraw.Draw(canvas)
    out = np.empty((len(chars), NORM, NORM), dtype=np.float32)
    for i, ch in enumerate(chars):
        draw.rectangle([0, 0, box, box], fill=0)
        draw.text((px * 0.4, px * 0.2), ch, font=pil_font, fill=255)
        # emulate the game's 16x16 rasterisation before normalising
        small = canvas.resize((16, 16), Image.BOX)
        out[i] = normalise(np.asarray(small, dtype=np.float32))
    return out


def scores(queries: np.ndarray, templates: np.ndarray) -> np.ndarray:
    q = queries.reshape(len(queries), -1)
    t = templates.reshape(len(templates), -1)
    return q @ t.T

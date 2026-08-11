"""Test whether the game font matches a font's embedded 16px bitmap strike.

Japanese TrueType fonts ship hand-tuned 16x16 bitmaps for small sizes, and PSP
games commonly reuse a font of that lineage.  If the game's glyphs came from such a
strike the correlation will be near-perfect rather than merely suggestive.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import charmatch2
from calibrate import KNOWN

FONTS = ["msgothic.ttc", "msmincho.ttc", "meiryo.ttc", "YuGothR.ttc", "YuGothB.ttc",
         "gulim.ttc", "batang.ttc", "simsun.ttc"]


def render_exact(chars: list[str], font_file: str, face: int, px: int, dx: int, dy: int) -> np.ndarray:
    pil_font = ImageFont.truetype(str(charmatch2.FONT_DIR / font_file), px, index=face)
    out = np.empty((len(chars), 16, 16), dtype=np.float32)
    canvas = Image.new("L", (16, 16))
    draw = ImageDraw.Draw(canvas)
    for i, ch in enumerate(chars):
        draw.rectangle([0, 0, 16, 16], fill=0)
        draw.text((dx, dy), ch, font=pil_font, fill=255)
        out[i] = np.asarray(canvas, dtype=np.float32)
    return out


def zncc(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a = a.reshape(len(a), -1) - a.reshape(len(a), -1).mean(axis=1, keepdims=True)
    b = b.reshape(len(b), -1) - b.reshape(len(b), -1).mean(axis=1, keepdims=True)
    an = np.linalg.norm(a, axis=1)
    bn = np.linalg.norm(b, axis=1)
    an[an == 0] = 1
    bn[bn == 0] = 1
    return np.sum(a * b, axis=1) / (an * bn)


def main() -> None:
    import font as fontlib
    raw = fontlib.tiles_to_glyphs(charmatch2.STREAM.read_bytes(),
                                  charmatch2.FONT_OFFSET, charmatch2.FONT_TILES).astype(np.float32)
    indices = sorted(KNOWN)
    targets = raw[indices] * 17.0
    chars = [KNOWN[i] for i in indices]

    print("font           face px  dx dy   mean ZNCC on known glyphs")
    best = []
    for font_file in FONTS:
        for face in range(4):
            for px in (15, 16, 17):
                for dx in (-1, 0, 1):
                    for dy in (-2, -1, 0, 1):
                        try:
                            rendered = render_exact(chars, font_file, face, px, dx, dy)
                        except Exception:  # noqa: BLE001
                            continue
                        if rendered.max() == 0:
                            continue
                        score = float(zncc(targets, rendered).mean())
                        best.append((score, font_file, face, px, dx, dy))
    best.sort(reverse=True)
    for score, font_file, face, px, dx, dy in best[:12]:
        print(f"{font_file:14s} {face:4d} {px:3d} {dx:3d}{dy:3d}   {score:.4f}")


if __name__ == "__main__":
    main()

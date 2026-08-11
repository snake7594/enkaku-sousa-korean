"""Prototype: render Hangul into the game's 16x16 4bpp glyph format.

Gulim and Dotum ship hand-tuned bitmap strikes at small pixel sizes, which is exactly
what a 16x16 cell wants — outline rendering scaled down turns Hangul into mush at this
size.  This compares the options so the test patch uses the legible one.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_DIR = Path(r"C:\Windows\Fonts")
CANDIDATES = [
    ("gulim.ttc", 0), ("gulim.ttc", 1), ("gulim.ttc", 2), ("gulim.ttc", 3),
    ("batang.ttc", 0), ("malgun.ttf", 0), ("malgunbd.ttf", 0),
]


def render(text: str, font_file: str, face: int, px: int, dx: int, dy: int) -> np.ndarray:
    pil = ImageFont.truetype(str(FONT_DIR / font_file), px, index=face)
    out = np.zeros((16, 16 * len(text)), dtype=np.uint8)
    canvas = Image.new("L", (16, 16))
    draw = ImageDraw.Draw(canvas)
    for i, ch in enumerate(text):
        draw.rectangle([0, 0, 16, 16], fill=0)
        draw.text((dx, dy), ch, font=pil, fill=255)
        out[:, i * 16 : (i + 1) * 16] = np.asarray(canvas, dtype=np.uint8)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", default="한글패치테스트중입니다")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--scale", type=int, default=5)
    args = parser.parse_args()

    rows = []
    labels = []
    for font_file, face in CANDIDATES:
        for px, dy in ((16, 0), (15, 0), (14, 1)):
            try:
                arr = render(args.text, font_file, face, px, 0, dy)
            except Exception:  # noqa: BLE001
                continue
            if arr.max() == 0:
                continue
            ink = (arr > 24).mean()
            rows.append(arr)
            labels.append(f"{font_file}#{face} px={px} dy={dy} ink={ink:.2f}")

    if not rows:
        print("nothing rendered")
        return
    width = max(r.shape[1] for r in rows)
    sheet = np.zeros((len(rows) * 18, width), dtype=np.uint8)
    for i, arr in enumerate(rows):
        sheet[i * 18 : i * 18 + 16, : arr.shape[1]] = arr
    image = Image.fromarray(sheet, "L")
    image.resize((width * args.scale, sheet.shape[0] * args.scale), Image.NEAREST).save(args.out)
    for i, label in enumerate(labels):
        print(f"   row {i}: {label}")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

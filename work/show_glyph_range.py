"""Render glyphs by index from the font, including past the 684 tiles the script uses.

The script's charmap stops at 684 tiles, which is 1368 glyphs, and that was taken for the whole
font.  It is not: the original stream1 keeps going with more kanji after it.  The system menu
indexes 存在 as 245 and 246, adjacent, which no part of the script's range provides -- so the
question is whether the menu counts from the start of that second region instead.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"D:\psp\원격수사")
LABEL = Path(r"C:\Windows\Fonts\consola.ttf")
TILE_BYTES = 256          # 32x16 at 4bpp, two glyphs side by side
FONT_AT = 0x80


def glyph(blob: bytes, index: int) -> np.ndarray:
    tile, half = divmod(index, 2)
    at = FONT_AT + tile * TILE_BYTES
    raw = np.frombuffer(blob[at:at + TILE_BYTES], dtype=np.uint8)
    nib = np.stack([raw & 0x0F, raw >> 4], axis=1).reshape(16, 32)
    return nib[:, half * 16:half * 16 + 16]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream1_orig.bin")
    parser.add_argument("indices", type=lambda v: int(v, 0), nargs="+")
    parser.add_argument("--scale", type=int, default=8)
    parser.add_argument("--cols", type=int, default=16)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    blob = args.stream.read_bytes()
    total = (len(blob) - FONT_AT) // TILE_BYTES * 2
    cells = [(i, glyph(blob, i)) for i in args.indices if 0 <= i < total]

    cols = min(args.cols, len(cells))
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("L", (cols * 17 * args.scale, rows * (17 * args.scale + 12)), 0)
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(str(LABEL), 11)
    for n, (index, cell) in enumerate(cells):
        r, c = divmod(n, cols)
        img = Image.fromarray((cell * 17).astype(np.uint8), "L").resize(
            (16 * args.scale, 16 * args.scale), Image.NEAREST)
        x, y = c * 17 * args.scale, r * (17 * args.scale + 12)
        sheet.paste(img, (x, y + 12))
        draw.text((x + 2, y), str(index), font=font, fill=200)
    sheet.save(args.out)
    print(f"font holds about {total} glyphs; showing {len(cells)} -> {args.out}")


if __name__ == "__main__":
    main()

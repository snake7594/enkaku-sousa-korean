"""Render the drawn glyphs to a PNG so they can actually be looked at.

Everything else about the font is checkable by machine -- slot counts, round-trip
losslessness, compressed size.  Legibility at 16x16 is not.  A glyph can occupy the right
slot, survive the tile conversion intact, and still be an unreadable smudge, and the only
way to find out is to look at it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

import font as fontlib

FONT_OFFSET = 0x80
FONT_TILES = 684


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", type=Path, required=True)
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--count", type=int, default=512)
    parser.add_argument("--columns", type=int, default=32)
    parser.add_argument("--scale", type=int, default=3)
    args = parser.parse_args()

    plain = args.stream.read_bytes()
    glyphs = fontlib.tiles_to_glyphs(plain, FONT_OFFSET, FONT_TILES)
    slots = json.loads(args.map.read_text(encoding="utf-8"))["slots"]
    ordered = sorted(slots.items(), key=lambda kv: kv[1])[:args.count]

    cols = args.columns
    rows = (len(ordered) + cols - 1) // cols
    sheet = np.zeros((rows * 17 + 1, cols * 17 + 1), dtype=np.uint8)
    for n, (_, index) in enumerate(ordered):
        r, c = divmod(n, cols)
        sheet[r * 17 + 1:r * 17 + 17, c * 17 + 1:c * 17 + 17] = glyphs[index] * 17

    image = Image.fromarray(255 - sheet, mode="L")
    image = image.resize((image.width * args.scale, image.height * args.scale), Image.NEAREST)
    image.save(args.out)
    print(f"{len(ordered)} glyphs, {rows}x{cols} -> {args.out} "
          f"({image.width}x{image.height})")
    print(f"   first row: {''.join(ch for ch, _ in ordered[:cols])}")


if __name__ == "__main__":
    main()

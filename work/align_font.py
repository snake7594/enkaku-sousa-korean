"""Sweep the byte alignment of a suspected glyph table and render the best fit.

Glyph tables are not necessarily 256-byte aligned (the script stream's table starts
at 0x80), so the row offset inside a tile has to be found before anything renders
correctly.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

import font as fontlib


def score_alignment(data: bytes, start: int, tiles: int, align: int) -> float:
    pixels = fontlib.tile_pixels(data, start + align)[:tiles]
    if len(pixels) == 0:
        return 0.0
    bearing = fontlib.is_glyph_tile(pixels).mean()
    # a glyph also keeps its bottom row clear more often than not
    bottom = (pixels[:, -1, :] < 2).all(axis=1).mean()
    return float(bearing + bottom)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--start", type=lambda v: int(v, 0), required=True)
    parser.add_argument("--tiles", type=int, default=64)
    parser.add_argument("--columns", type=int, default=24)
    parser.add_argument("--scale", type=int, default=4)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    data = args.path.read_bytes()
    scores = [(score_alignment(data, args.start, args.tiles, a), a) for a in range(0, 256, 16)]
    scores.sort(reverse=True)
    print("alignment scores (best first):")
    for score, align in scores[:6]:
        print(f"   +0x{align:02x}  {score:.3f}")

    best_align = scores[0][1]
    glyphs = fontlib.tiles_to_glyphs(data, args.start + best_align, args.tiles)
    image = fontlib.sheet(glyphs, columns=args.columns)
    image.resize((image.width * args.scale, image.height * args.scale), Image.NEAREST).save(args.out)
    print(f"best align +0x{best_align:02x} -> 0x{args.start + best_align:x}, {len(glyphs)} glyphs -> {args.out}")


if __name__ == "__main__":
    main()

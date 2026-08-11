"""Render specific glyph indices large, to check a code -> index hypothesis by eye."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

import font as fontlib

STREAM = Path(r"D:\psp\원격수사\font_extract\script_stream.bin")
FONT_OFFSET = 0x80
FONT_TILES = 684


def load_glyphs() -> np.ndarray:
    return fontlib.tiles_to_glyphs(STREAM.read_bytes(), FONT_OFFSET, FONT_TILES)


def strip(glyphs: np.ndarray, indices: list[int], scale: int = 6, per_line: int = 24) -> Image.Image:
    lines = [indices[i : i + per_line] for i in range(0, len(indices), per_line)]
    width = max(len(line) for line in lines) * 16
    canvas = np.zeros((len(lines) * 16, width), dtype=np.uint8)
    for r, line in enumerate(lines):
        for c, index in enumerate(line):
            if 0 <= index < len(glyphs):
                canvas[r * 16 : r * 16 + 16, c * 16 : c * 16 + 16] = glyphs[index] * 17
    image = Image.fromarray(canvas, "L")
    return image.resize((width * scale, canvas.shape[0] * scale), Image.NEAREST)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("indices", type=lambda v: int(v, 0), nargs="+")
    parser.add_argument("--scale", type=int, default=6)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    glyphs = load_glyphs()
    print(f"{len(glyphs)} glyphs available; showing {args.indices}")
    strip(glyphs, args.indices, args.scale).save(args.out)
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

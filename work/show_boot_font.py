"""Render glyphs from the font the menu uses, which lives inside BOOT.BIN.

The disassembly settles what a year of guessing could not.  0x884be84 picks one of two font
bases depending on where the string sits -- 0x88EA760, inside the executable, for strings in
the executable itself, and the stream1 table for script text -- and 0x884bfb8 turns a
character into an offset from whichever was picked:

    index = (lead - 0x88) * 253 + trail
    glyph = base + (index >> 1) * 256

That is the same arithmetic the dialogue uses, which is why the byte pairs looked familiar and
the characters did not: the menu was never addressing the dialogue font.  253 never appeared
in a search for the constant because the compiler builds it as ((x << 6) - x) << 2) + x.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"D:\psp\원격수사")
BOOT = ROOT / "iso_extract" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN"
LABEL = Path(r"C:\Windows\Fonts\consola.ttf")
VADDR_TO_FILE = 0x8803FAC
KANJI_FONT = 0x88EA760      # used for strings inside the executable
TILE = 256


def glyph(blob: bytes, base: int, index: int) -> np.ndarray:
    tile, half = divmod(index, 2)
    at = base + tile * TILE
    raw = np.frombuffer(blob[at:at + TILE], dtype=np.uint8)
    if len(raw) < TILE:
        return np.zeros((16, 16), dtype=np.uint8)
    nib = np.stack([raw & 0x0F, raw >> 4], axis=1).reshape(16, 32)
    return nib[:, half * 16:half * 16 + 16]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=BOOT)
    parser.add_argument("--base", type=lambda v: int(v, 0), default=KANJI_FONT)
    parser.add_argument("indices", type=lambda v: int(v, 0), nargs="+")
    parser.add_argument("--scale", type=int, default=8)
    parser.add_argument("--cols", type=int, default=16)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    blob = args.file.read_bytes()
    base = args.base - VADDR_TO_FILE
    cells = [(i, glyph(blob, base, i)) for i in args.indices]
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
    print(f"font at {args.base:#x} (file {base:#x}); {len(cells)} glyphs -> {args.out}")


if __name__ == "__main__":
    main()

"""Render every duplicate slot in a flat grid so they can be read in a few passes.

Grouping by character puts two glyphs on a row and needs 204 rows, which is too tall to read.
A flat grid of fixed width fits the same 423 slots into a handful of screens, and the slot
number for any cell follows from its position, printed alongside.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

import font as fontlib
import lzss

ROOT = Path(r"D:\psp\원격수사")
CHARMAP = ROOT / "font_extract" / "charmap_final.json"
ORIGINAL = ROOT / "iso_extract" / "PSP_GAME" / "USRDIR" / "0000"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cols", type=int, default=20)
    parser.add_argument("--page", type=int, default=0)
    parser.add_argument("--rows", type=int, default=8)
    parser.add_argument("--scale", type=int, default=4)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    plain = lzss.decompress(ORIGINAL.read_bytes(), 0x27E000)[0]
    glyphs = fontlib.tiles_to_glyphs(plain, 0x80, 684)
    charmap = json.loads(CHARMAP.read_text(encoding="utf-8"))

    slots_of = defaultdict(list)
    for i, e in enumerate(charmap):
        if e.get("char"):
            slots_of[e["char"]].append(i)
    dup = sorted({s for c, ss in slots_of.items() if len(ss) > 1 for s in ss})
    per_page = args.cols * args.rows
    pages = (len(dup) + per_page - 1) // per_page
    chunk = dup[args.page * per_page:(args.page + 1) * per_page]
    print(f"{len(dup)} duplicate slots, page {args.page + 1}/{pages}, {len(chunk)} shown")

    cell = 18
    sheet = np.zeros((args.rows * cell + 1, args.cols * cell + 1), dtype=np.uint8)
    for n, slot in enumerate(chunk):
        r, c = divmod(n, args.cols)
        sheet[r * cell + 1:r * cell + 17, c * cell + 1:c * cell + 17] = glyphs[slot] * 17

    for r in range(args.rows):
        row = chunk[r * args.cols:(r + 1) * args.cols]
        if row:
            print(f"  row {r}: " + " ".join(
                f"{s}({charmap[s]['char']})" for s in row))

    out = args.out or ROOT / "build" / f"dup_page{args.page}.png"
    image = Image.fromarray(255 - sheet, mode="L")
    image.resize((image.width * args.scale, image.height * args.scale),
                 Image.NEAREST).save(out)
    print(f"-> {out}")


if __name__ == "__main__":
    main()

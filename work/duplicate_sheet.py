"""Render the slots that share a character, so the glyphs can be told apart by eye.

Context can suggest which reading a slot needs; only the bitmap says which character the
slot actually draws.  Every misreading in this project came from a slot resolved to the
wrong character, and 204 characters own more than one slot, so the ambiguity is structural
rather than incidental.

The sheet puts the slots that collide next to each other at a readable size.  Two glyphs
assigned the same character will look like two different kanji, and which is which is then
a matter of reading them rather than inferring them.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

import font as fontlib

ROOT = Path(r"D:\psp\원격수사")
CHARMAP = ROOT / "font_extract" / "charmap_final.json"
STREAM = ROOT / "build" / "stream1_ko_font_clean.bin"
ORIGINAL = ROOT / "iso_extract" / "PSP_GAME" / "USRDIR" / "0000"
FONT_OFFSET, FONT_TILES = 0x80, 684


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chars", default="度画箍駆毎沢過撃示屈恋",
                        help="characters whose colliding slots to render")
    parser.add_argument("--all", action="store_true", help="render every duplicate")
    parser.add_argument("--scale", type=int, default=5)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "duplicate_slots.png")
    args = parser.parse_args()

    # the Japanese glyphs live in the untouched archive, not in the Korean font build
    import lzss
    plain = lzss.decompress(ORIGINAL.read_bytes(), 0x27E000)[0]
    glyphs = fontlib.tiles_to_glyphs(plain, FONT_OFFSET, FONT_TILES)

    charmap = json.loads(CHARMAP.read_text(encoding="utf-8"))
    slots_of = defaultdict(list)
    for i, e in enumerate(charmap):
        if e.get("char"):
            slots_of[e["char"]].append(i)
    duplicates = {c: s for c, s in slots_of.items() if len(s) > 1}

    wanted = (sorted(duplicates, key=lambda c: -len(duplicates[c]))
              if args.all else [c for c in args.chars if c in duplicates])
    rows = [(c, duplicates[c]) for c in wanted]
    width = max(len(s) for _, s in rows)
    print(f"{len(rows)} characters, up to {width} colliding slots each")

    cell = 18
    sheet = np.zeros((len(rows) * cell + 1, width * cell + 1), dtype=np.uint8)
    for r, (char, slots) in enumerate(rows):
        for c, slot in enumerate(slots[:width]):
            sheet[r * cell + 1:r * cell + 17, c * cell + 1:c * cell + 17] = glyphs[slot] * 17
        print(f"   row {r:2d}  {char}  slots {slots}")

    image = Image.fromarray(255 - sheet, mode="L")
    image = image.resize((image.width * args.scale, image.height * args.scale),
                         Image.NEAREST)
    image.save(args.out)
    print(f"-> {args.out} ({image.width}x{image.height})")


if __name__ == "__main__":
    main()

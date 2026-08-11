"""Overwrite specific glyph slots with Hangul — a font-only change.

The previous test put Korean into rarely used slots, and the game drew the original
kanji there.  Since no second copy of the glyph table exists anywhere in the data, the
likely explanation is that the font was already resident in memory.  Replacing a glyph
that appears constantly makes the answer unmistakable: glyphs 107 and 108 are 光 and
志, the protagonist's name, so every line of dialogue shows whether the patch took.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import font as fontlib
from make_test_patch import FONT_OFFSET, FONT_TILES, render_hangul


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, required=True, help="decompressed stream 1")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--set", action="append", nargs=2, metavar=("SLOT", "CHAR"),
                        required=True, help="e.g. --set 107 한 --set 108 글")
    args = parser.parse_args()

    plain = bytearray(args.src.read_bytes())
    glyphs = fontlib.tiles_to_glyphs(bytes(plain), FONT_OFFSET, FONT_TILES)

    # sanity: the glyph<->tile conversion must round-trip exactly, or the whole font
    # would be quietly corrupted by writing it back
    if fontlib.glyphs_to_tiles(glyphs) != bytes(plain[FONT_OFFSET : FONT_OFFSET + FONT_TILES * 256]):
        raise SystemExit("glyph/tile conversion is not lossless — refusing to write")

    slots = [(int(slot), char) for slot, char in args.set]
    rendered = render_hangul("".join(char for _, char in slots))
    for (slot, char), bitmap in zip(slots, rendered):
        glyphs[slot] = bitmap
        print(f"   slot {slot} <- {char}")

    tiles = fontlib.glyphs_to_tiles(glyphs)
    plain[FONT_OFFSET : FONT_OFFSET + len(tiles)] = tiles
    args.out.write_bytes(bytes(plain))
    print(f"-> {args.out} ({len(plain)} bytes, size unchanged)")


if __name__ == "__main__":
    main()

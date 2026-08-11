"""Find characters the typeface could not draw.

Two tofu boxes are visible in the rendered sheet.  A missing glyph is invisible to every
other check -- the slot is assigned, the tile round-trips, the stream compresses -- and only
shows up in game as a blank where a word should be, so it is worth naming the characters
rather than counting them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import font as fontlib

STREAM = Path(r"D:\psp\원격수사\build\stream1_ko_font_clean.bin")
MAP = Path(r"D:\psp\원격수사\build\korean_slots_full_clean.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", type=Path, default=STREAM)
    parser.add_argument("--map", type=Path, default=MAP)
    parser.add_argument("--font", type=Path,
                        default=Path(r"D:\psp\타임트레블러즈\SeoulHangangB.ttf"))
    args = parser.parse_args()

    glyphs = fontlib.tiles_to_glyphs(args.stream.read_bytes(), 0x80, 684)
    slots = json.loads(args.map.read_text(encoding="utf-8"))["slots"]

    blank = [(c, i) for c, i in slots.items() if not glyphs[i].any()]
    print(f"{len(blank)} blank glyphs: "
          f"{[(c, f'U+{ord(c):04X}', i) for c, i in blank]}")

    faint = sorted(((c, int(glyphs[i].sum()), i) for c, i in slots.items()
                    if 0 < glyphs[i].sum() < 150), key=lambda x: x[1])
    print(f"\n{len(faint)} very light glyphs (ink sum < 150):")
    for ch, ink, index in faint[:14]:
        print(f"   {ch!r} U+{ord(ch):04X} slot {index}: ink {ink}")

    # a character the typeface lacks still draws -- as .notdef, a hollow box -- so it
    # passes the blank test and only the cmap can tell it apart from a real glyph
    from fontTools.ttLib import TTFont
    ttf = TTFont(str(args.font))
    covered = set()
    for table in ttf["cmap"].tables:
        covered |= set(table.cmap)
    missing = [c for c in slots if ord(c) not in covered]
    print(f"\ntypeface covers {len(covered)} code points; "
          f"{len(missing)} of the {len(slots)} assigned characters are missing from it:")
    for ch in missing:
        print(f"   {ch!r} U+{ord(ch):04X} slot {slots[ch]} -- drawn as .notdef")


if __name__ == "__main__":
    main()

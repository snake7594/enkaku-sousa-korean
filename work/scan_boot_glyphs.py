"""Find which glyphs of the executable's font no string uses.

The font at 0x88EA760 holds about 1950 glyphs and only two of its tiles are blank, so putting
Hangul in it means overwriting something.  Overwriting a glyph some string still needs would
corrupt that string, and the only way to know which are safe is to read every string in the
file and collect what they reference.

So this walks the whole loaded segment, decodes every NUL-terminated run that looks like game
text, and counts each glyph index it sees.  A run counts as text only if it is mostly kana and
kanji and ends properly -- random data decodes into something, and without that filter the
"used" set swallows the font.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
BOOT = ROOT / "iso_extract" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN"
VADDR_TO_FILE = 0x8803FAC
KANJI_FONT = 0x88EA760
# The font runs from file 0xe67b4 to 0x101cb4 and the strings begin immediately after it.  A
# first pass put the boundary at 1952 glyphs, which swallowed the strings and reported that
# nothing referenced anything.
FONT_TILES = 436
MAX_INDEX = FONT_TILES * 2
FONT_END = 0x101CB4


def is_text_byte(b: int) -> bool:
    return (0x28 <= b < 0x7B or 0x81 <= b < 0xA0 or 0xA7 <= b < 0xDE
            or 0xE0 <= b < 0xFD or b in (0x0A, 0x0D))


def scan(blob: bytes, start: int, end: int):
    """Yield (offset, length, [glyph indices]) for each plausible string."""
    i = start
    while i < end:
        if blob[i] == 0:
            i += 1
            continue
        run = i
        indices, good, total = [], 0, 0
        while run < end and blob[run]:
            b = blob[run]
            total += 1
            if 0x81 <= b < 0xA0 or 0xE0 <= b < 0xFD:
                if run + 1 >= end:
                    break
                code = (b << 8) | blob[run + 1]
                if code >= 0x8800:
                    index = ((code - 0x8800) >> 8) * 253 + (code & 0xFF)
                    if 0 <= index < MAX_INDEX:
                        indices.append(index)
                # both bytes count as good; adding one to `good` and two to `total` put a
                # string of pure kanji at 0.5 and the filter threw away every one of them
                good += 2
                run += 2
                total += 1
                continue
            if is_text_byte(b):
                good += 1
            run += 1
        length = run - i
        if length >= 3 and total and good / total > 0.9:
            yield i, length, indices
        i = run + 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=BOOT)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "boot_glyph_use.json")
    args = parser.parse_args()

    blob = args.file.read_bytes()
    phoff, = struct.unpack_from("<I", blob, 28)
    p_offset, p_vaddr, _, p_filesz = struct.unpack_from("<4I", blob, phoff + 4)
    font_start = KANJI_FONT - VADDR_TO_FILE

    used = {}
    strings = 0
    for lo, hi in ((p_offset, font_start), (FONT_END, p_offset + p_filesz)):
        for offset, length, indices in scan(blob, lo, min(hi, len(blob))):
            strings += 1
            for index in indices:
                used[index] = used.get(index, 0) + 1

    free = [i for i in range(MAX_INDEX) if i not in used]
    args.out.write_text(json.dumps({
        "schema": "enkaku_boot_glyph_use_v1", "strings_scanned": strings,
        "glyphs_used": len(used), "glyphs_free": len(free),
        "font_vaddr": KANJI_FONT, "font_file": font_start,
        "free": free}, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{strings} plausible strings scanned in {p_offset:#x}..{font_start:#x}")
    print(f"{len(used)} glyph indices referenced, {len(free)} never referenced")
    runs, start, last = [], None, None
    for i in free:
        if start is None:
            start = last = i
        elif i == last + 1:
            last = i
        else:
            runs.append((start, last))
            start = last = i
    if start is not None:
        runs.append((start, last))
    runs.sort(key=lambda r: r[0] - r[1])
    print("\nlongest unreferenced runs:")
    for a, b in runs[:12]:
        print(f"   {a}..{b}  ({b - a + 1} glyphs)")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

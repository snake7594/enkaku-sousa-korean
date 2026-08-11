"""Test 3: switch to Seoul Hangang B, and find where the usable glyph range ends.

Slots 107/108 took the patch and showed Hangul in game; slots 1349-1358 did not and
drew their original kanji.  Nothing in the data explains that — there is only one copy
of the glyph table — so the likely cause is that the engine loads fewer glyphs than the
table contains, leaving the high indices pointing at whatever was in memory.

So this writes one distinct syllable into each of a spread of slots and rewrites a line
to reference them in order.  Whichever positions come out Hangul are inside the range,
and the first kanji marks the cutoff.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

import font as fontlib
import lzss
from compare_hangul_fonts import HANGANG, render
from decode_script import HIRA, HIRA_BASE, KANJI_LO, LEAD_HI, LEAD_LO
from extract_all_text import decode_run
from make_test_patch import FONT_OFFSET, FONT_TILES, encode_glyph

SRC = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR\0000")
STREAM1 = 0x27E000
IDEOGRAPHIC_SPACE = bytes([0x81, 0x40])

PROBE_SLOTS = [200, 400, 600, 800, 1000, 1100, 1200, 1300, 1340, 1360]
PROBE_CHARS = "가나다라마바사아자차"
NAME_SLOTS = {107: "한", 108: "글"}


def run_end(plain: bytes, start: int) -> int:
    end = start
    n = len(plain)
    while end < n:
        b = plain[end]
        if b == 0x0F:
            end += 2 if (0x31 <= plain[end + 1] <= 0x39) else 1
        elif b == 0x11:
            end += 1
        elif b == 0x16:
            end += 2
        elif LEAD_LO <= b <= LEAD_HI:
            end += 2
        elif HIRA_BASE <= b < HIRA_BASE + len(HIRA) or 0xA1 <= b <= 0xDF:
            end += 1
        else:
            break
    return end


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offset", type=lambda v: int(v, 0), default=0x13F069)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--px", type=int, default=16)
    parser.add_argument("--dy", type=int, default=0)
    parser.add_argument("--hangang", type=Path, default=HANGANG)
    args = parser.parse_args()

    plain = bytearray(lzss.decompress(SRC.read_bytes(), STREAM1)[0])

    end = run_end(bytes(plain), args.offset)
    budget = end - args.offset
    print(f"line at 0x{args.offset:x}: {budget} bytes")

    # keep the speaker-name block and the newline after it
    prefix_end = args.offset
    if plain[prefix_end : prefix_end + 2] == b"\x81\x79":
        while prefix_end < end and plain[prefix_end : prefix_end + 2] != b"\x81\x7a":
            prefix_end += 2
        prefix_end += 2
        if prefix_end < end and plain[prefix_end] == 0x11:
            prefix_end += 1
    prefix = bytes(plain[args.offset : prefix_end])

    body = b"".join(encode_glyph(slot) for slot in PROBE_SLOTS)
    room = budget - len(prefix)
    if len(body) > room:
        raise SystemExit(f"probe needs {len(body)} bytes, only {room} available")
    pad = IDEOGRAPHIC_SPACE * ((room - len(body)) // 2)
    tail = b"\x11" * (room - len(body) - len(pad))
    plain[args.offset : end] = prefix + body + pad + tail

    # draw everything with Seoul Hangang B
    glyphs = fontlib.tiles_to_glyphs(bytes(plain), FONT_OFFSET, FONT_TILES)
    if fontlib.glyphs_to_tiles(glyphs) != bytes(plain[FONT_OFFSET : FONT_OFFSET + FONT_TILES * 256]):
        raise SystemExit("glyph/tile conversion is not lossless — refusing to write")

    targets = list(NAME_SLOTS.items()) + list(zip(PROBE_SLOTS, PROBE_CHARS))
    bitmaps = render("".join(ch for _, ch in targets), args.hangang, args.px, 0, args.dy,
                     supersample=4)
    for (slot, ch), bitmap in zip(targets, bitmaps):
        glyphs[slot] = bitmap
    print(f"   name slots: {NAME_SLOTS}")
    print(f"   probe slots: {dict(zip(PROBE_SLOTS, PROBE_CHARS))}")

    tiles = fontlib.glyphs_to_tiles(glyphs)
    plain[FONT_OFFSET : FONT_OFFSET + len(tiles)] = tiles

    args.out.write_bytes(bytes(plain))
    print(f"   new line: {decode_run(bytes(plain), args.offset, end)[0][:60]}")
    print(f"-> {args.out} ({len(plain)} bytes, size unchanged)")


if __name__ == "__main__":
    main()

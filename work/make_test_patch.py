"""Build a Hangul test patch: put Korean glyphs in spare slots and rewrite one line.

Two things are proven at once — that glyph bitmaps can be replaced and that a line can
be re-encoded to reference them.  Both edits stay inside the decompressed stream and
keep its size, so the archive and the ISO keep every offset they had.

Gulim's embedded 16px bitmap strike is used for the glyphs: outline fonts scaled to
16x16 turn Hangul into mush, while the strike is a hand-tuned bitmap of exactly the
size the game wants.

The replacement text is written over the original bytes and padded with the ideographic
space, so the line occupies the same number of bytes and every pointer in the script
bytecode stays valid.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import font as fontlib
import lzss
from decode_script import HIRA, HIRA_BASE, KANJI_LO, LEAD_HI, LEAD_LO
from extract_all_text import decode_run, find_runs

SRC = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR\0000")
STREAM1 = 0x27E000
FONT_OFFSET = 0x80
FONT_TILES = 684

GULIM = Path(r"C:\Windows\Fonts\gulim.ttc")
IDEOGRAPHIC_SPACE = bytes([0x81, 0x40])


def render_hangul(chars: str, px: int = 16, face: int = 0) -> np.ndarray:
    """(n, 16, 16) coverage values 0..15, from Gulim's bitmap strike."""
    pil = ImageFont.truetype(str(GULIM), px, index=face)
    out = np.zeros((len(chars), 16, 16), dtype=np.uint8)
    canvas = Image.new("L", (16, 16))
    draw = ImageDraw.Draw(canvas)
    for i, ch in enumerate(chars):
        draw.rectangle([0, 0, 16, 16], fill=0)
        draw.text((0, 0), ch, font=pil, fill=255)
        out[i] = (np.asarray(canvas, dtype=np.uint16) * 15 // 255).astype(np.uint8)
    return out


def encode_glyph(index: int) -> bytes:
    from decode_script import kanji_code
    return kanji_code(index)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offset", type=lambda v: int(v, 0), default=0x13F069,
                        help="offset of the text run to rewrite")
    parser.add_argument("--text", default="한글패치테스트입니다",
                        help="Korean text to show, after the speaker name")
    parser.add_argument("--first-slot", type=int, default=1349)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    data = SRC.read_bytes()
    plain, _ = lzss.decompress(data, STREAM1)
    plain = bytearray(plain)

    # locate the run and see how many bytes we may use
    runs = find_runs(bytes(plain), args.offset, min_tokens=1, min_wide=0)
    run_start, run_text = next((r for r in runs if r[0] == args.offset), (None, None))
    if run_start is None:
        raise SystemExit(f"no text run starts at 0x{args.offset:x}")
    end = args.offset
    while end < len(plain):
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
    budget = end - args.offset
    print(f"run at 0x{args.offset:x}: {budget} bytes")
    print(f"   original: {run_text[:70]}")

    # keep the speaker name block 【..】 and the line break that follows it
    prefix_end = args.offset
    if plain[prefix_end : prefix_end + 2] == b"\x81\x79":
        while prefix_end < end and plain[prefix_end : prefix_end + 2] != b"\x81\x7a":
            prefix_end += 2
        prefix_end += 2
        if prefix_end < end and plain[prefix_end] == 0x11:
            prefix_end += 1
    prefix = bytes(plain[args.offset : prefix_end])

    unique = list(dict.fromkeys(args.text))
    slots = {ch: args.first_slot + i for i, ch in enumerate(unique)}
    if args.first_slot + len(unique) > FONT_TILES * 2:
        raise SystemExit("not enough glyph slots")
    print(f"   {len(unique)} distinct syllables -> slots "
          f"{args.first_slot}..{args.first_slot + len(unique) - 1}")

    body = b"".join(encode_glyph(slots[ch]) for ch in args.text)
    room = budget - len(prefix)
    if len(body) > room:
        raise SystemExit(f"text needs {len(body)} bytes but only {room} are available")
    pad = IDEOGRAPHIC_SPACE * ((room - len(body)) // 2)
    tail = b"\x11" * (room - len(body) - len(pad))
    new_bytes = prefix + body + pad + tail
    assert len(new_bytes) == budget
    plain[args.offset : end] = new_bytes

    # draw the syllables into the spare glyph slots
    glyphs = fontlib.tiles_to_glyphs(bytes(plain), FONT_OFFSET, FONT_TILES)
    rendered = render_hangul("".join(unique))
    for ch, bitmap in zip(unique, rendered):
        glyphs[slots[ch]] = bitmap
    tiles = fontlib.glyphs_to_tiles(glyphs)
    plain[FONT_OFFSET : FONT_OFFSET + len(tiles)] = tiles

    args.out.write_bytes(bytes(plain))
    print(f"   new line : {decode_run(bytes(plain), args.offset, end)[0][:70]}")
    print(f"-> {args.out} ({len(plain)} bytes, size unchanged)")


if __name__ == "__main__":
    main()

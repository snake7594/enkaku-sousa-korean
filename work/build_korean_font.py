"""Build the Korean font: assign glyph slots and draw them into the archive's table.

Slots come from the two-byte range only — 1368 of them, addressed as
(lead-0x88)*253+trail — because that path is verified working in game.  The one-byte
range would be cheaper per character but lives in a table inside BOOT.BIN whose exact
start is still unconfirmed, and getting it wrong would corrupt every single-byte
character, so it is left alone for now.

Characters are assigned in order of how often the translation uses them, which keeps
the common ones in the low slots and makes the table easy to reason about.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import font as fontlib
import lzss
from decode_script import kanji_code

SRC = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR\0000")
STREAM1 = 0x27E000
FONT_OFFSET = 0x80
FONT_TILES = 684
TOTAL_SLOTS = FONT_TILES * 2

HANGANG = Path(r"D:\psp\타임트레블러즈\SeoulHangangB.ttf")

# punctuation the engine already draws from its own Shift-JIS block; no slot needed
PASSTHROUGH = set("　、。！？（）「」【】…・")


def render(
    chars: str,
    font_path: Path,
    px: int,
    dy: int,
    supersample: int = 4,
) -> np.ndarray:
    """Rasterise each glyph at its original size into a fresh 16x16 cell.

    The game advances this two-byte glyph table in 16-pixel cells.  Do not crop
    or scale the Korean bitmap to make it fit a guessed baseline: that changes
    the visible font size.  Render the requested face size directly into a
    fresh cell, with only the explicit cell offset applied.  A two-pixel pad is
    used around the working canvas so the supersampled draw never clips at the
    edges before it is reduced back to the native 16x16 cell.
    """
    scale = supersample
    face = ImageFont.truetype(str(font_path), px * scale)
    pad = 2
    canvas_size = (16 + pad * 2) * scale
    out = np.zeros((len(chars), 16, 16), dtype=np.uint8)

    for index, ch in enumerate(chars):
        canvas = Image.new("L", (canvas_size, canvas_size), 0)
        draw = ImageDraw.Draw(canvas)
        draw.text(
            (pad * scale, pad * scale + dy * scale),
            ch,
            font=face,
            fill=255,
        )
        reduced = canvas.resize((16 + pad * 2, 16 + pad * 2), Image.Resampling.BOX)
        cell = reduced.crop((pad, pad, pad + 16, pad + 16))
        bitmap = (np.asarray(cell, dtype=np.uint16) * 15 // 255).astype(np.uint8)
        if not np.any(bitmap):
            raise ValueError(f"font has no visible glyph for U+{ord(ch):04X}")
        out[index] = bitmap
    return out


def collect(translation: Path) -> Counter:
    counts = Counter()
    for line in translation.read_text(encoding="utf-8").splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        for ch in parts[2].replace("\\n", ""):
            if ch in PASSTHROUGH or ch.isspace():
                continue
            counts[ch] += 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translation", type=Path, required=True,
                        help="TSV: offset / lines / Korean text")
    parser.add_argument("--out-stream", type=Path, required=True)
    parser.add_argument("--out-map", type=Path, required=True)
    parser.add_argument("--font", type=Path, default=HANGANG)
    parser.add_argument("--px", type=int, default=16)
    parser.add_argument("--dy", type=int, default=0)
    args = parser.parse_args()

    counts = collect(args.translation)
    print(f"{sum(counts.values())} characters in the translation, {len(counts)} distinct")
    if len(counts) > TOTAL_SLOTS:
        print(f"   !! {len(counts) - TOTAL_SLOTS} more than the {TOTAL_SLOTS} slots available; "
              f"the rarest will be dropped")

    ordered = [ch for ch, _ in counts.most_common(TOTAL_SLOTS)]
    mapping = {ch: index for index, ch in enumerate(ordered)}

    plain = bytearray(lzss.decompress(SRC.read_bytes(), STREAM1)[0])
    glyphs = fontlib.tiles_to_glyphs(bytes(plain), FONT_OFFSET, FONT_TILES)
    if fontlib.glyphs_to_tiles(glyphs) != bytes(plain[FONT_OFFSET : FONT_OFFSET + FONT_TILES * 256]):
        raise SystemExit("glyph/tile conversion is not lossless — refusing to write")

    bitmaps = render("".join(ordered), args.font, args.px, args.dy)
    for ch, bitmap in zip(ordered, bitmaps):
        glyphs[mapping[ch]] = bitmap
    plain[FONT_OFFSET : FONT_OFFSET + FONT_TILES * 256] = fontlib.glyphs_to_tiles(glyphs)

    args.out_stream.write_bytes(bytes(plain))
    args.out_map.write_text(json.dumps(
        {"font": str(args.font), "px": args.px, "dy": args.dy,
         "render_mode": "native_cell_no_crop_no_scale", "cell": [16, 16],
         "slots": {ch: mapping[ch] for ch in ordered},
         "codes": {ch: kanji_code(mapping[ch]).hex() for ch in ordered}},
        ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"   {len(ordered)} glyphs drawn into slots 0..{len(ordered) - 1}")
    print(f"-> {args.out_stream} ({len(plain)} bytes, size unchanged)")
    print(f"-> {args.out_map}")


if __name__ == "__main__":
    main()

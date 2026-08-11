"""Pin down the kana font inside BOOT.BIN.

Single-byte codes (0x28-0x7A hiragana, 0xA1-0xDF half-width katakana) are drawn from a
glyph table in the executable, not from the archive.  Those 146 codes are the cheapest
storage the format offers — one byte per character — so the Korean patch wants them for
its most frequent syllables, which means finding exactly where index 0 sits.

The table is in ordinary gojūon order, so the offset is found by rendering that
sequence with a Japanese font and sliding it over the file, scoring the match.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import font as fontlib

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")
GULIM = Path(r"C:\Windows\Fonts\msgothic.ttc")

HIRA = ("ぁあぃいぅうぇえぉおかがきぎくぐけげこごさざしじすずせぜそぞ"
        "ただちぢっつづてでとどなにぬねのはばぱひびぴふぶぷへべぺほぼぽ"
        "まみむめもゃやゅゆょよらりるれろゎわゐゑをん")


def reference(chars: str, px: int = 16, face: int = 0) -> np.ndarray:
    pil = ImageFont.truetype(str(GULIM), px, index=face)
    out = np.zeros((len(chars), 16, 16), dtype=np.float32)
    canvas = Image.new("L", (16, 16))
    draw = ImageDraw.Draw(canvas)
    for i, ch in enumerate(chars):
        draw.rectangle([0, 0, 16, 16], fill=0)
        draw.text((0, 0), ch, font=pil, fill=255)
        out[i] = np.asarray(canvas, dtype=np.float32) / 255.0
    return out


def normalise(block: np.ndarray) -> np.ndarray:
    flat = block.reshape(len(block), -1).astype(np.float32)
    flat = flat - flat.mean(axis=1, keepdims=True)
    norms = np.linalg.norm(flat, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return flat / norms


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="start", type=lambda v: int(v, 0), default=0x88000)
    parser.add_argument("--to", dest="stop", type=lambda v: int(v, 0), default=0x9C000)
    parser.add_argument("--count", type=int, default=40, help="kana used for matching")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    data = BOOT.read_bytes()
    ref = normalise(reference(HIRA[: args.count]))

    best = []
    for offset in range(args.start, args.stop, 16):
        glyphs = fontlib.tiles_to_glyphs(data, offset, (args.count + 1) // 2 + 1)
        if len(glyphs) < args.count:
            continue
        cand = normalise(glyphs[: args.count].astype(np.float32))
        score = float((cand * ref).sum(axis=1).mean())
        best.append((score, offset))

    best.sort(reverse=True)
    print("best offsets for hiragana index 0 (ぁ):")
    for score, offset in best[:8]:
        print(f"   0x{offset:06x}  mean correlation {score:.3f}")

    top = best[0][1]
    print(f"\nkana table starts at 0x{top:x}")
    print(f"   hiragana ぁ..ん  = indices 0..82   -> codes 0x28..0x7A")
    print(f"   katakana follows = indices 83..    -> half-width codes 0xA1..0xDF")

    if args.out:
        glyphs = fontlib.tiles_to_glyphs(data, top, 96)
        image = fontlib.sheet(glyphs[:170], columns=24)
        image.resize((image.width * 4, image.height * 4), Image.NEAREST).save(args.out)
        print(f"-> {args.out}")


if __name__ == "__main__":
    main()

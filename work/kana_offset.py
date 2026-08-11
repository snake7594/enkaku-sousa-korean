"""Confirm where hiragana index 0 sits in the BOOT.BIN kana table.

Reading the offset off a rendered sheet is error-prone by a glyph or two, and being
off by one would corrupt every single-byte character in the patch.  So the candidate
offsets are scored by matching the game's glyphs against rendered kana with the same
shape-normalised comparison used for the kanji, which tolerates the difference in
drawing style far better than raw pixel correlation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

import charmatch2
import font as fontlib
from decode_script import HIRA

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")
BASE = 0x92060   # tile-aligned start of the region that contains the table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=lambda v: int(v, 0), default=BASE)
    parser.add_argument("--count", type=int, default=60)
    parser.add_argument("--search", type=int, default=40)
    args = parser.parse_args()

    data = BOOT.read_bytes()
    glyphs = fontlib.tiles_to_glyphs(data, args.base, 140)
    normed = np.stack([charmatch2.normalise(g.astype(np.float32)) for g in glyphs])

    sample = HIRA[: args.count]
    templates = np.stack([
        charmatch2.normalise(np.asarray(im, dtype=np.float32))
        for im in _render_each(sample)
    ])

    print(f"matching {args.count} kana against glyphs from 0x{args.base:x}")
    scores = []
    for shift in range(args.search):
        window = normed[shift : shift + args.count]
        if len(window) < args.count:
            break
        value = float(np.mean([
            (window[i].reshape(-1) * templates[i].reshape(-1)).sum()
            for i in range(args.count)
        ]))
        scores.append((value, shift))

    scores.sort(reverse=True)
    for value, shift in scores[:6]:
        print(f"   hiragana index 0 at glyph +{shift:3d}  mean similarity {value:.3f}")

    best = scores[0][1]
    print(f"\nhiragana ぁ = glyph {best} from 0x{args.base:x}")
    print(f"   code 0x28..0x7A -> glyph {best}..{best + 82}")


def _render_each(chars: str):
    from PIL import Image, ImageDraw, ImageFont
    pil = ImageFont.truetype(str(charmatch2.FONT_DIR / "msgothic.ttc"), 16, index=0)
    for ch in chars:
        canvas = Image.new("L", (16, 16))
        ImageDraw.Draw(canvas).text((0, 0), ch, font=pil, fill=255)
        yield canvas


if __name__ == "__main__":
    main()

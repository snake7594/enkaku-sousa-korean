"""Find the second glyph atlas -- the one the system menu indexes into.

The menu writes 存在 as slots 245 and 246, adjacent.  In the script font those two characters
sit at 183 and 143, and I read both glyphs myself, so the menu is not using that atlas.  No
index-to-Shift-JIS table exists in BOOT.BIN either -- there is not one run of consecutive
Shift-JIS kanji codes anywhere in it.  That leaves a second atlas, somewhere.

Glyph data has a shape that ordinary code and data do not.  At 4 bits per pixel a 16x16 glyph
is 128 bytes, and across a run of them the ink covers roughly a fifth to a half of each cell,
never all of it and never none of it, with the same figure repeating cell after cell.  Scoring
that over a sliding window finds bitmap fonts without knowing anything else about the format.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(r"D:\psp\원격수사")
ISO = ROOT / "iso_extract"

GLYPH_BYTES = 128     # 16x16 at 4bpp


def glyphiness(blob: bytes, offset: int, count: int) -> float:
    """How much a run of `count` cells looks like 4bpp glyphs."""
    chunk = blob[offset:offset + count * GLYPH_BYTES]
    if len(chunk) < count * GLYPH_BYTES:
        return 0.0
    cells = np.frombuffer(chunk, dtype=np.uint8).reshape(count, GLYPH_BYTES)
    lo, hi = cells & 0x0F, cells >> 4
    ink = ((lo > 0).sum(axis=1) + (hi > 0).sum(axis=1)) / 256.0
    # a page of glyphs: most cells carry ink, none is solid, none is empty
    good = ((ink > 0.12) & (ink < 0.62)).mean()
    varied = float(ink.std())
    return good * min(1.0, varied * 8)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", nargs="*", default=[
        "PSP_GAME/SYSDIR/BOOT.BIN", "PSP_GAME/USRDIR/0001", "PSP_GAME/USRDIR/0002",
        "PSP_GAME/USRDIR/0003", "PSP_GAME/USRDIR/0004", "PSP_GAME/USRDIR/0011"])
    parser.add_argument("--window", type=int, default=64, help="glyphs per scored window")
    parser.add_argument("--step", type=int, default=128)
    parser.add_argument("--top", type=int, default=6)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "menu_font_scan.json")
    args = parser.parse_args()

    results = {}
    for rel in args.files:
        path = ISO / rel
        if not path.exists():
            print(f"{rel}: missing")
            continue
        blob = path.read_bytes()
        scores = []
        for offset in range(0, len(blob) - args.window * GLYPH_BYTES, args.step):
            s = glyphiness(blob, offset, args.window)
            if s > 0.55:
                scores.append((s, offset))
        scores.sort(reverse=True)
        # keep the best offset per neighbourhood
        picked, seen = [], []
        for s, offset in scores:
            if any(abs(offset - o) < args.window * GLYPH_BYTES for o in seen):
                continue
            seen.append(offset)
            picked.append({"offset": offset, "score": round(s, 3)})
            if len(picked) >= args.top:
                break
        results[rel] = picked
        print(f"{rel:34s} {len(blob):>10d} bytes, {len(scores)} windows score > 0.55")
        for p in picked:
            print(f"      {p['offset']:#010x}  score {p['score']}")

    args.out.write_text(json.dumps({"schema": "enkaku_menu_font_scan_v1", "hits": results},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

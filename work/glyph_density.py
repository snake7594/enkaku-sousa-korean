"""Sort glyphs by ink density. Kana are far lighter than kanji, so if the kana
block lives in this font it shows up as a contiguous low-density cluster."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

import font as fontlib
from showglyph import load_glyphs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--group", type=int, default=32)
    args = parser.parse_args()

    glyphs = load_glyphs()
    density = (glyphs > 2).mean(axis=(1, 2))
    print(f"{len(glyphs)} glyphs, density min={density.min():.3f} max={density.max():.3f}")

    print("\nmean ink density per block of {}:".format(args.group))
    for start in range(0, len(glyphs), args.group):
        block = density[start : start + args.group]
        bar = "#" * int(block.mean() * 60)
        print(f"   {start:5d}-{start + len(block) - 1:5d}  {block.mean():.3f}  {bar}")

    lightest = np.argsort(density)[:96]
    print("\nlightest glyph indices:", sorted(int(i) for i in lightest))
    if args.out:
        fontlib.sheet(glyphs[sorted(lightest)], columns=24).resize((24 * 16 * 4, 4 * 16 * 4)).save(args.out)
        print(f"-> {args.out}")


if __name__ == "__main__":
    main()

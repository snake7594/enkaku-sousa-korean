"""Pick the size/offset for Seoul Hangang B that fills the 16x16 cell without clipping.

Bolder is easier to read once the engine's black outline is applied, but a size that
looks fine on common syllables can clip the tall 받침 of rarer ones.  So the check runs
over a spread of syllables and rejects any setting whose ink reaches the cell edge.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from compare_hangul_fonts import HANGANG, render

# a spread that stresses height (double 받침), width, and the vowel extremes
SAMPLE = "가힣곪뷁왕뿌쨈끝윻뢨겷삵훑짧뚫웩앓넓밟읊꿇쐐excelPQ0189，。？！"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hangang", type=Path, default=HANGANG)
    args = parser.parse_args()

    print(f"{'setting':22s} {'ink':>5s} {'top':>4s} {'bot':>4s} {'left':>5s} {'right':>6s}  verdict")
    best = []
    for px in (13, 14, 15, 16, 17):
        for dy in (-2, -1, 0, 1):
            for dx in (-1, 0, 1):
                glyphs = render(SAMPLE, args.hangang, px, dx, dy, supersample=4)
                if glyphs.max() == 0:
                    continue
                ink = float((glyphs > 2).mean())
                top = int((glyphs[:, 0, :] > 2).sum())
                bottom = int((glyphs[:, 15, :] > 2).sum())
                left = int((glyphs[:, :, 0] > 2).sum())
                right = int((glyphs[:, :, 15] > 2).sum())
                clipped = top + bottom + left + right
                verdict = "clips" if clipped else "clean"
                if not clipped:
                    best.append((ink, px, dx, dy))
                print(f"px{px} dx{dx:+d} dy{dy:+d}       {ink:.3f} {top:4d} {bottom:4d} "
                      f"{left:5d} {right:6d}  {verdict}")

    if best:
        best.sort(reverse=True)
        ink, px, dx, dy = best[0]
        print(f"\nbest clean setting: px={px} dx={dx} dy={dy} (ink {ink:.3f})")
    else:
        print("\nno setting avoids clipping entirely")


if __name__ == "__main__":
    main()

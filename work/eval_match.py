"""Evaluate the shape-normalised matcher on the hand-identified glyphs."""

from __future__ import annotations

import argparse

import numpy as np

import charmatch2
from calibrate import KNOWN

FONTS = [
    ("YuGothB.ttc", 0), ("YuGothM.ttc", 0), ("msgothic.ttc", 0),
    ("meiryo.ttc", 0), ("msmincho.ttc", 0), ("YuGothR.ttc", 0),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topk", type=int, default=5)
    parser.add_argument("--fonts", type=int, default=len(FONTS))
    args = parser.parse_args()

    glyphs = charmatch2.game_glyphs()
    chars = charmatch2.cp932_candidates()
    print(f"{len(glyphs)} glyphs vs {len(chars)} candidates, norm={charmatch2.NORM} blur={charmatch2.BLUR}")

    per_font = []
    for font_file, face in FONTS[: args.fonts]:
        templates = charmatch2.render_normalised(chars, font_file, face)
        s = charmatch2.scores(glyphs, templates)
        per_font.append(s)
        order = np.argsort(-s, axis=1)[:, : args.topk]
        hits = sum(chars[order[i, 0]] == c for i, c in KNOWN.items())
        top = sum(c in [chars[j] for j in order[i]] for i, c in KNOWN.items())
        print(f"   {font_file:14s} top1 {hits:2d}/{len(KNOWN)}  top{args.topk} {top:2d}/{len(KNOWN)}")

    combined = np.mean(per_font, axis=0)
    order = np.argsort(-combined, axis=1)[:, : args.topk]
    hits = top = 0
    for index, expected in KNOWN.items():
        ranked = [chars[j] for j in order[index]]
        hits += ranked[0] == expected
        top += expected in ranked
        mark = "ok  " if ranked[0] == expected else "MISS"
        print(f"   {mark} glyph {index:4d} expect {expected}  got {' '.join(ranked)}")
    print(f"\ncombined: top1 {hits}/{len(KNOWN)}  top{args.topk} {top}/{len(KNOWN)}")


if __name__ == "__main__":
    main()

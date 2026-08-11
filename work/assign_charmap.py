"""Resolve the glyph -> character mapping as a global assignment problem.

Two things fix most of what plain nearest-neighbour matching gets wrong:

  * the candidate pool is restricted to JIS X 0208 level 1 kanji plus kana and
    symbols.  Level 2 holds thousands of rare characters that a detective drama
    never uses, and they were absorbing most of the bad matches.
  * the font has no duplicate glyphs, so each character may be used at most once.
    Solving that as an optimal assignment stops a handful of "attractor" shapes
    from being chosen for dozens of different glyphs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

import charmatch2
from calibrate import KNOWN

FONTS = [("YuGothB.ttc", 0), ("YuGothM.ttc", 0), ("msgothic.ttc", 0),
         ("meiryo.ttc", 0), ("msmincho.ttc", 0), ("YuGothR.ttc", 0)]


def sjis_range(lead_lo: int, trail_lo: int, lead_hi: int, trail_hi: int) -> list[str]:
    chars = []
    for lead in range(lead_lo, lead_hi + 1):
        for trail in range(0x40, 0xFD):
            if trail == 0x7F:
                continue
            if lead == lead_lo and trail < trail_lo:
                continue
            if lead == lead_hi and trail > trail_hi:
                continue
            try:
                ch = bytes([lead, trail]).decode("cp932")
            except UnicodeDecodeError:
                continue
            if len(ch) == 1:
                chars.append(ch)
    return chars


def candidate_pool(level2: bool) -> list[str]:
    # JIS level 1 kanji: 0x889F .. 0x9872
    pool = sjis_range(0x88, 0x9F, 0x98, 0x72)
    # symbols, latin, kana rows 0x81-0x83
    pool += sjis_range(0x81, 0x40, 0x83, 0xFC)
    if level2:
        pool += sjis_range(0x98, 0x9F, 0xEA, 0xA4)
    seen, out = set(), []
    for ch in pool:
        if ch not in seen:
            seen.add(ch)
            out.append(ch)
    return out


def visual_scores(glyphs: np.ndarray, chars: list[str]) -> np.ndarray:
    total = np.zeros((len(glyphs), len(chars)), dtype=np.float32)
    for font_file, face in FONTS:
        templates = charmatch2.render_normalised(chars, font_file, face)
        total += charmatch2.scores(glyphs, templates)
        print(f"   rendered {font_file}")
    return total / len(FONTS)


def report(name: str, chars: list[str], picks: np.ndarray) -> int:
    hits = 0
    for index, expected in sorted(KNOWN.items()):
        got = chars[picks[index]]
        hits += got == expected
    print(f"{name}: top1 {hits}/{len(KNOWN)}")
    return hits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--level2", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--topk", type=int, default=8)
    args = parser.parse_args()

    glyphs = charmatch2.game_glyphs()
    chars = candidate_pool(args.level2)
    print(f"{len(glyphs)} glyphs vs {len(chars)} candidates (level2={args.level2})")

    scores = visual_scores(glyphs, chars)

    greedy = np.argmax(scores, axis=1)
    report("argmax", chars, greedy)

    rows, cols = linear_sum_assignment(-scores)
    assigned = np.empty(len(glyphs), dtype=int)
    assigned[rows] = cols
    report("assignment", chars, assigned)

    for index, expected in sorted(KNOWN.items()):
        order = np.argsort(-scores[index])[: args.topk]
        mark = "ok  " if chars[assigned[index]] == expected else "MISS"
        print(f"   {mark} glyph {index:4d} expect {expected}  assigned {chars[assigned[index]]}  "
              f"top{args.topk} {' '.join(chars[j] for j in order)}")

    if args.out:
        table = []
        for i in range(len(glyphs)):
            order = np.argsort(-scores[i])[: args.topk]
            table.append({
                "index": i,
                "assigned": chars[assigned[i]],
                "assigned_score": round(float(scores[i, assigned[i]]), 4),
                "best": chars[order[0]],
                "best_score": round(float(scores[i, order[0]]), 4),
                "alts": [chars[j] for j in order],
            })
        args.out.write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"table -> {args.out}")


if __name__ == "__main__":
    main()

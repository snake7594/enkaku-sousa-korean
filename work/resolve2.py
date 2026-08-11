"""Improved glyph -> character resolver.

Three passes over the same evidence:

  1. every ruby annotation proposes the dictionary words whose reading and length
     fit, scored by bitmap similarity;
  2. glyphs that came out unanimously are then treated as fixed, and the pairs are
     re-scored with that knowledge — a settled glyph disambiguates every other
     annotation it appears in, so this converges quickly;
  3. glyphs no annotation ever covers are matched by bitmap alone, as a global
     assignment against the characters not already spoken for (the font has no
     duplicate glyphs, so a character can only be used once).

Each entry is tagged with the evidence behind it so low-confidence rows can be
checked by eye rather than trusted blindly.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

import charmatch2
import ruby
from assign_charmap import candidate_pool, visual_scores
from calibrate import KNOWN
from resolve_charmap import build_reading_index

FIXED_BONUS = 3.0


def score_word(word: str, base: tuple[int, ...], scores: np.ndarray,
               char_pos: dict[str, int], fixed: dict[int, str]) -> float | None:
    total = 0.0
    for glyph, ch in zip(base, word):
        if ch not in char_pos:
            return None
        total += float(scores[glyph, char_pos[ch]])
        if fixed.get(glyph) == ch:
            total += FIXED_BONUS
        elif glyph in fixed:
            total -= FIXED_BONUS
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()

    counts = ruby.all_pairs()
    print("building reading index ...")
    index = build_reading_index()

    glyphs = charmatch2.game_glyphs()
    chars = candidate_pool(level2=True)
    char_pos = {c: i for i, c in enumerate(chars)}
    print(f"scoring {len(glyphs)} glyphs x {len(chars)} candidates ...")
    scores = visual_scores(glyphs, chars)

    usable = []
    for (base, reading), count in counts.items():
        if any(g >= len(glyphs) for g in base):
            continue
        words = [w for w in index.get(reading, ()) if len(w) == len(base)]
        if words:
            usable.append((base, reading, count, words))
    print(f"{len(usable)} ruby pairs have a dictionary match")

    fixed: dict[int, str] = {}
    votes: dict[int, Counter] = {}
    for round_no in range(args.rounds):
        votes = defaultdict(Counter)
        chosen = {}
        for base, reading, count, words in usable:
            best, best_score = None, None
            for word in words:
                value = score_word(word, base, scores, char_pos, fixed)
                if value is not None and (best_score is None or value > best_score):
                    best, best_score = word, value
            if best is None:
                continue
            chosen[(base, reading)] = best
            for glyph, ch in zip(base, best):
                votes[glyph][ch] += count

        new_fixed = {}
        for glyph, counter in votes.items():
            top_char, top_count = counter.most_common(1)[0]
            if top_count == sum(counter.values()):        # unanimous
                new_fixed[glyph] = top_char
        changed = sum(1 for g, c in new_fixed.items() if fixed.get(g) != c)
        fixed = new_fixed
        print(f"round {round_no + 1}: {len(chosen)} pairs resolved, "
              f"{len(fixed)} glyphs unanimous ({changed} changed)")

    # accuracy on the hand-identified glyphs
    hits = total = 0
    for glyph, expected in sorted(KNOWN.items()):
        if glyph not in votes:
            continue
        got = votes[glyph].most_common(1)[0][0]
        total += 1
        hits += got == expected
        mark = "ok  " if got == expected else "MISS"
        print(f"   {mark} glyph {glyph:4d} expect {expected} got {got}")
    print(f"known-glyph accuracy on annotated ones: {hits}/{total}")

    # pass 3: bitmap-only glyphs, assigned against the characters still free
    taken = {votes[g].most_common(1)[0][0] for g in votes}
    free_idx = [i for i, c in enumerate(chars) if c not in taken]
    unknown = [g for g in range(len(glyphs)) if g not in votes]
    print(f"\n{len(unknown)} glyphs have no ruby evidence; assigning against "
          f"{len(free_idx)} unused characters")
    sub = scores[np.ix_(unknown, free_idx)]
    rows, cols = linear_sum_assignment(-sub)
    bitmap_pick = {unknown[r]: free_idx[c] for r, c in zip(rows, cols)}

    table = []
    for glyph in range(len(glyphs)):
        if glyph in votes:
            counter = votes[glyph]
            top_char, top_count = counter.most_common(1)[0]
            agreement = top_count / sum(counter.values())
            table.append({
                "index": glyph,
                "char": top_char,
                "source": "ruby",
                "confidence": "high" if agreement == 1.0 and top_count >= 2 else "medium",
                "agreement": round(agreement, 3),
                "votes": top_count,
                "alts": [c for c, _ in counter.most_common()[1:4]],
            })
        else:
            pick = bitmap_pick.get(glyph)
            order = np.argsort(-scores[glyph])[:6]
            table.append({
                "index": glyph,
                "char": chars[pick] if pick is not None else chars[order[0]],
                "source": "bitmap",
                "confidence": "low",
                "score": round(float(scores[glyph, order[0]]), 4),
                "alts": [chars[j] for j in order],
            })

    args.out.write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")
    tiers = Counter(e["confidence"] for e in table)
    print(f"\ntable -> {args.out}")
    print(f"confidence tiers: {dict(tiers)}")


if __name__ == "__main__":
    main()

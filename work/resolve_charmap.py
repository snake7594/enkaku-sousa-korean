"""Resolve glyph -> character using furigana readings, with bitmap similarity as tiebreak.

Every ruby annotation states the reading of a known-length run of glyphs.  Inverting
pykakasi's kanji dictionary gives, for a reading, every word that is pronounced that
way; intersecting that with the run's length usually leaves a handful of words, and
the bitmap similarity picks between them.  Glyphs appearing in several annotations
accumulate votes, so the result is far more reliable than shape matching alone.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from pykakasi.kanji import Kanwa

import charmatch2
import ruby
from assign_charmap import candidate_pool, visual_scores
from calibrate import KNOWN


def build_reading_index() -> dict[str, set[str]]:
    """reading -> set of words, inverted from the kanwa dictionary."""
    kanwa = Kanwa()
    index: dict[str, set[str]] = defaultdict(set)
    for lead in range(0x88, 0xF0):
        for trail in range(0x40, 0xFD):
            if trail == 0x7F:
                continue
            try:
                ch = bytes([lead, trail]).decode("cp932")
            except UnicodeDecodeError:
                continue
            if len(ch) != 1:
                continue
            bucket = kanwa.load(ch)
            if not bucket:
                continue
            for word, entries in bucket.items():
                for entry in entries:
                    reading = entry[0]
                    if not isinstance(reading, str):
                        continue
                    index[reading].add(word)
                    tail = entry[1] if len(entry) > 1 else None
                    for suffix in (tail if isinstance(tail, list) else [tail]):
                        if isinstance(suffix, str) and suffix:
                            index[reading + suffix].add(word)
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--min-count", type=int, default=1)
    args = parser.parse_args()

    counts = ruby.all_pairs()
    glyph_set = {g for base, _ in counts for g in base}
    print(f"{sum(counts.values())} ruby instances, {len(counts)} distinct pairs, "
          f"{len(glyph_set)} glyphs annotated")

    print("building reading index from the kanji dictionary ...")
    index = build_reading_index()
    print(f"   {len(index)} distinct readings, {sum(len(v) for v in index.values())} word entries")

    glyphs = charmatch2.game_glyphs()
    chars = candidate_pool(level2=True)
    char_pos = {c: i for i, c in enumerate(chars)}
    print(f"scoring {len(glyphs)} glyphs against {len(chars)} candidates ...")
    scores = visual_scores(glyphs, chars)

    votes: dict[int, Counter] = defaultdict(Counter)
    solved_pairs = 0
    for (base, reading), count in counts.items():
        if count < args.min_count:
            continue
        if any(g >= len(glyphs) for g in base):
            continue  # stray refs from spans that were actually bytecode
        words = [w for w in index.get(reading, ()) if len(w) == len(base)]
        if not words:
            continue
        best_word, best_score = None, -1e9
        for word in words:
            if any(c not in char_pos for c in word):
                continue
            total = sum(scores[g, char_pos[c]] for g, c in zip(base, word))
            if total > best_score:
                best_word, best_score = word, total
        if best_word is None:
            continue
        solved_pairs += 1
        for g, c in zip(base, best_word):
            votes[g][c] += count

    print(f"\n{solved_pairs}/{len(counts)} ruby pairs matched a dictionary word; "
          f"{len(votes)} glyphs received votes")

    resolved = {g: counter.most_common(1)[0] for g, counter in votes.items()}
    hits = total = 0
    for index_, expected in sorted(KNOWN.items()):
        if index_ in resolved:
            got, weight = resolved[index_]
            total += 1
            hits += got == expected
            mark = "ok  " if got == expected else "MISS"
            print(f"   {mark} glyph {index_:4d} expect {expected} got {got} (votes {weight})")
    print(f"known-glyph check: {hits}/{total} of the annotated ones correct")

    if args.out:
        table = []
        for i in range(len(glyphs)):
            entry = {"index": i}
            if i in resolved:
                char, weight = resolved[i]
                alts = votes[i].most_common()
                entry.update(char=char, source="ruby", votes=weight,
                             agreement=round(weight / sum(votes[i].values()), 3),
                             alts=[c for c, _ in alts[1:4]])
            else:
                order = np.argsort(-scores[i])[:6]
                entry.update(char=chars[order[0]], source="bitmap",
                             score=round(float(scores[i, order[0]]), 4),
                             alts=[chars[j] for j in order[1:]])
            table.append(entry)
        args.out.write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")
        ruby_n = sum(1 for e in table if e["source"] == "ruby")
        print(f"\ntable -> {args.out}  ({ruby_n} ruby-resolved, {len(table) - ruby_n} bitmap-only)")


if __name__ == "__main__":
    main()

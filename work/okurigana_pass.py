"""Resolve the remaining glyphs from okurigana (inflectional kana endings).

The kanji dictionary stores inflected forms as whole keys — 戻ら / 戻り / 戻る / 戻れ /
戻ろ — so a kanji followed by kana in the script narrows the candidates to those that
take that ending.  One ending on its own is weak (hundreds of kanji precede る), but a
verb shows up across several inflections, and a glyph seen with る, り, った and れ is
compatible with only a handful of characters.  Evidence is therefore accumulated over
every distinct ending a glyph appears with, and the bitmap decides among the survivors.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from pykakasi.kanji import Kanwa

import charmatch2
from assign_charmap import candidate_pool, visual_scores
from calibrate import KNOWN
from improve_charmap import is_kanji, runs_in
from decode_script import STREAM, text_spans

KANA_RANGE = ("ぁ", "ヿ")
MISS_PENALTY = 0.35
VISUAL_WEIGHT = 4.0


def is_kana(ch: str) -> bool:
    return KANA_RANGE[0] <= ch <= KANA_RANGE[1]


def build_okurigana_index(max_run: int = 2) -> dict[tuple[int, str], set[str]]:
    """(kanji run length, kana ending) -> kanji runs that take that ending."""
    kanwa = Kanwa()
    index: dict[tuple[int, str], set[str]] = defaultdict(set)
    for lead in range(0x88, 0xF0):
        for trail in range(0x40, 0xFD):
            if trail == 0x7F:
                continue
            try:
                ch = bytes([lead, trail]).decode("cp932")
            except UnicodeDecodeError:
                continue
            if len(ch) != 1 or not is_kanji(ch):
                continue
            for word in (kanwa.load(ch) or {}):
                head = 0
                while head < len(word) and is_kanji(word[head]):
                    head += 1
                tail = word[head:]
                if head == 0 or head > max_run or not tail:
                    continue
                if not all(is_kana(c) for c in tail):
                    continue
                index[(head, tail)].add(word[:head])
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--charmap", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--min-tails", type=int, default=2,
                        help="distinct endings a glyph must show before it is decided")
    args = parser.parse_args()

    table = json.loads(args.charmap.read_text(encoding="utf-8"))
    resolved = {e["index"]: e["char"] for e in table if e["source"] != "bitmap"}
    unresolved = [e["index"] for e in table if e["source"] == "bitmap"]
    print(f"{len(resolved)} glyphs already resolved, {len(unresolved)} to go")

    print("indexing inflected forms ...")
    index = build_okurigana_index()
    print(f"   {len(index)} (length, ending) buckets")

    glyphs = charmatch2.game_glyphs()
    chars = candidate_pool(level2=True)
    char_pos = {c: i for i, c in enumerate(chars)}
    print(f"scoring {len(glyphs)} glyphs x {len(chars)} candidates ...")
    scores = visual_scores(glyphs, chars)

    # collect the endings each single-glyph run is followed by
    tails: dict[int, Counter] = defaultdict(Counter)
    for _, span in text_spans(STREAM.read_bytes()):
        for run, tail in runs_in(span):
            if len(run) != 1 or not tail or run[0] >= len(glyphs):
                continue
            for width in (1, 2):
                if len(tail) >= width:
                    tails[run[0]][tail[:width]] += 1

    taken = set(resolved.values())
    picks: dict[int, tuple[str, int, int]] = {}
    for glyph in unresolved:
        observed = tails.get(glyph)
        if not observed:
            continue
        buckets = []
        for ending, count in observed.items():
            candidates = index.get((1, ending))
            if candidates:
                buckets.append((candidates, count))
        if len(buckets) < args.min_tails:
            continue

        support: Counter = Counter()
        for candidates, count in buckets:
            for word in candidates:
                support[word] += count
        total_weight = sum(count for _, count in buckets)

        best, best_score = None, None
        for word, weight in support.items():
            if word in taken or word not in char_pos:
                continue
            missed = total_weight - weight
            value = weight - MISS_PENALTY * missed + VISUAL_WEIGHT * float(scores[glyph, char_pos[word]])
            if best_score is None or value > best_score:
                best, best_score = word, value
        if best is not None:
            picks[glyph] = (best, len(buckets), support[best])
            taken.add(best)

    print(f"\n{len(picks)} of the remaining glyphs decided from okurigana")

    hits = total = 0
    for glyph, expected in sorted(KNOWN.items()):
        if glyph in picks:
            total += 1
            hits += picks[glyph][0] == expected
            mark = "ok  " if picks[glyph][0] == expected else "MISS"
            print(f"   {mark} glyph {glyph:4d} expect {expected} got {picks[glyph][0]}")
    if total:
        print(f"   known-glyph check: {hits}/{total}")

    out = []
    for entry in table:
        glyph = entry["index"]
        if glyph in picks:
            char, n_tails, weight = picks[glyph]
            out.append({"index": glyph, "char": char, "source": "okurigana",
                        "confidence": "medium" if n_tails >= 3 else "low",
                        "endings": n_tails, "support": weight,
                        "alts": entry.get("alts", [])})
        else:
            out.append(entry)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tiers = Counter((e["source"], e["confidence"]) for e in out)
    print(f"\ntable -> {args.out}")
    for key, n in sorted(tiers.items()):
        print(f"   {key[0]:10s} {key[1]:8s} {n}")


if __name__ == "__main__":
    main()

"""Decide the remaining ruby-annotated glyphs from per-character readings.

The earlier ruby pass required the whole annotated word to exist in the dictionary,
which throws away names and compounds the dictionary never heard of — exactly the
cases that were left unresolved.  Here the reading is matched per character instead:
a single-glyph annotation is compared against every kanji with that reading, and a
multi-glyph one is split across its glyphs in every way the readings allow.  The
bitmap then chooses among the survivors.
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
from improve_charmap import is_kanji

KANA = ("ぁ", "ヿ")


def is_kana(ch: str) -> bool:
    return KANA[0] <= ch <= KANA[1]


def build_char_readings() -> dict[str, set[str]]:
    """reading -> kanji that can be read that way (stem readings included)."""
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
            if len(ch) != 1 or not is_kanji(ch):
                continue
            for word, entries in (kanwa.load(ch) or {}).items():
                if not word.startswith(ch):
                    continue
                tail = word[1:]
                if tail and not all(is_kana(c) for c in tail):
                    continue
                for entry in entries:
                    reading = entry[0]
                    if not isinstance(reading, str) or not reading:
                        continue
                    if not tail:
                        index[reading].add(ch)
                    elif reading.endswith(tail) and len(reading) > len(tail):
                        index[reading[: -len(tail)]].add(ch)
    return index


def splits(reading: str, parts: int, index: dict[str, set[str]]):
    """Every way to cut the reading into `parts` pieces that are all real readings."""
    if parts == 1:
        if reading in index:
            yield (reading,)
        return
    for cut in range(1, len(reading) - parts + 2):
        head = reading[:cut]
        if head not in index:
            continue
        for rest in splits(reading[cut:], parts - 1, index):
            yield (head,) + rest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--charmap", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-base", type=int, default=4)
    args = parser.parse_args()

    table = json.loads(args.charmap.read_text(encoding="utf-8"))
    resolved = {e["index"]: e["char"] for e in table if e["source"] != "bitmap"}
    unresolved = {e["index"] for e in table if e["source"] == "bitmap"}
    print(f"{len(unresolved)} glyphs unresolved")

    print("indexing per-character readings ...")
    index = build_char_readings()
    print(f"   {len(index)} readings")

    glyphs = charmatch2.game_glyphs()
    chars = candidate_pool(level2=True)
    char_pos = {c: i for i, c in enumerate(chars)}
    print(f"scoring {len(glyphs)} glyphs x {len(chars)} candidates ...")
    scores = visual_scores(glyphs, chars)

    votes: dict[int, Counter] = defaultdict(Counter)
    used_pairs = 0
    for (base, reading), count in ruby.all_pairs().items():
        if not (1 <= len(base) <= args.max_base):
            continue
        if any(g >= len(glyphs) for g in base):
            continue
        if not any(g in unresolved for g in base):
            continue
        best, best_score = None, None
        for combo in splits(reading, len(base), index):
            options = [index[part] for part in combo]
            choice, total = [], 0.0
            ok = True
            for glyph, candidates in zip(base, options):
                if glyph in resolved:
                    fixed = resolved[glyph]
                    if fixed not in candidates:
                        ok = False
                        break
                    choice.append(fixed)
                    total += 2.0
                    continue
                pick = max((c for c in candidates if c in char_pos),
                           key=lambda c: scores[glyph, char_pos[c]], default=None)
                if pick is None:
                    ok = False
                    break
                choice.append(pick)
                total += float(scores[glyph, char_pos[pick]])
            if not ok:
                continue
            if best_score is None or total > best_score:
                best, best_score = choice, total
        if best is None:
            continue
        used_pairs += 1
        for glyph, ch in zip(base, best):
            if glyph in unresolved:
                votes[glyph][ch] += count

    print(f"\n{used_pairs} ruby pairs usable; {len(votes)} unresolved glyphs got a reading match")

    taken = set(resolved.values())
    picks = {}
    for glyph, counter in votes.items():
        for ch, _ in counter.most_common():
            if ch not in taken:
                picks[glyph] = ch
                taken.add(ch)
                break

    out = []
    for entry in table:
        glyph = entry["index"]
        if glyph in picks:
            out.append({"index": glyph, "char": picks[glyph], "source": "reading",
                        "confidence": "medium", "alts": entry.get("alts", [])})
        else:
            out.append(entry)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    tiers = Counter((e["source"], e["confidence"]) for e in out)
    print(f"{len(picks)} newly decided\ntable -> {args.out}")
    for key, n in sorted(tiers.items()):
        print(f"   {key[0]:10s} {key[1]:8s} {n}")

    for glyph in sorted(picks)[:20]:
        print(f"   glyph {glyph:4d} -> {picks[glyph]}")


if __name__ == "__main__":
    main()

"""Resolve the ruby-less glyphs from word context.

A kanji run in the script is a word.  Once some of its glyphs are known, the
dictionary narrows the rest sharply: a two-character run beginning with 被 can only
be 被害, 被疑, 被告 and a handful more, and the bitmap picks between those.  Trailing
kana help too — a dictionary entry records its okurigana, so 違/ちが plus う confirms
the entry where a bare shape comparison could not.

Newly settled glyphs become anchors for the next pass, so coverage grows outward
from the ruby-annotated core.
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
from decode_script import (HALFWIDTH, HIRA, HIRA_BASE, KANJI_HI, KANJI_LO,
                           LEAD_HI, LEAD_LO, STREAM, kanji_index, text_spans)

KANJI_RANGE = (0x4E00, 0x9FA5)


def is_kanji(ch: str) -> bool:
    return KANJI_RANGE[0] <= ord(ch) <= KANJI_RANGE[1]


def kana_of(b: int) -> str | None:
    if HIRA_BASE <= b < HIRA_BASE + len(HIRA):
        return HIRA[b - HIRA_BASE]
    if 0xA1 <= b <= 0xDF:
        return HALFWIDTH[b - 0xA1]
    return None


def runs_in(span: bytes) -> list[tuple[tuple[int, ...], str]]:
    """(glyph run, kana immediately following it)."""
    tokens: list[tuple[str, object]] = []
    i, n = 0, len(span)
    while i < n:
        b = span[i]
        if b == 0x0F:
            i += 2 if (i + 1 < n and 0x31 <= span[i + 1] <= 0x39) else 1
            tokens.append(("break", None))
        elif b < 0x20:
            i += 2 if b == 0x16 else 1
            tokens.append(("break", None))
        elif LEAD_LO <= b <= LEAD_HI and i + 1 < n:
            if KANJI_LO <= b <= KANJI_HI:
                tokens.append(("kanji", kanji_index(b, span[i + 1])))
            else:
                tokens.append(("break", None))
            i += 2
        else:
            kana = kana_of(b)
            tokens.append(("kana", kana) if kana else ("break", None))
            i += 1

    out = []
    i = 0
    while i < len(tokens):
        if tokens[i][0] != "kanji":
            i += 1
            continue
        run = []
        while i < len(tokens) and tokens[i][0] == "kanji":
            run.append(int(tokens[i][1]))
            i += 1
        tail = []
        j = i
        while j < len(tokens) and tokens[j][0] == "kana" and len(tail) < 4:
            tail.append(tokens[j][1])
            j += 1
        out.append((tuple(run), "".join(tail)))
    return out


def build_word_index() -> tuple[dict[int, list[str]], dict[str, set[str]]]:
    """words grouped by length, plus word -> set of okurigana tails."""
    kanwa = Kanwa()
    by_len: dict[int, list[str]] = defaultdict(list)
    tails: dict[str, set[str]] = defaultdict(set)
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
            bucket = kanwa.load(ch) or {}
            for word, entries in bucket.items():
                if not all(is_kanji(c) for c in word):
                    continue
                by_len[len(word)].append(word)
                for entry in entries:
                    tail = entry[1] if len(entry) > 1 else None
                    for suffix in (tail if isinstance(tail, list) else [tail]):
                        if isinstance(suffix, str) and suffix:
                            tails[word].add(suffix)
    for words in by_len.values():
        words.sort()
    return by_len, tails


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--charmap", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=4)
    parser.add_argument("--max-run", type=int, default=4)
    args = parser.parse_args()

    table = json.loads(args.charmap.read_text(encoding="utf-8"))
    # anything already decided by evidence stronger than bare shape matching anchors
    # this pass, and none of it may be overwritten
    known: dict[int, str] = {e["index"]: e["char"] for e in table if e["source"] != "bitmap"}
    by_source = Counter(e["source"] for e in table if e["source"] != "bitmap")
    print(f"anchors: {len(known)} glyphs {dict(by_source)}")

    print("indexing dictionary words ...")
    by_len, tails = build_word_index()
    print(f"   {sum(len(v) for v in by_len.values())} kanji-only words")

    position_index: dict[tuple[int, int, str], set[str]] = defaultdict(set)
    for length, words in by_len.items():
        if length > args.max_run:
            continue
        for word in words:
            for pos, ch in enumerate(word):
                position_index[(length, pos, ch)].add(word)

    glyphs = charmatch2.game_glyphs()
    chars = candidate_pool(level2=True)
    char_pos = {c: i for i, c in enumerate(chars)}
    print(f"scoring {len(glyphs)} glyphs x {len(chars)} candidates ...")
    scores = visual_scores(glyphs, chars)

    print("collecting kanji runs ...")
    run_counts = Counter()
    for _, span in text_spans(STREAM.read_bytes()):
        for run, tail in runs_in(span):
            if 2 <= len(run) <= args.max_run and all(g < len(glyphs) for g in run):
                run_counts[(run, tail)] += 1
    print(f"   {len(run_counts)} distinct runs")

    resolved = dict(known)
    for round_no in range(args.rounds):
        votes: dict[int, Counter] = defaultdict(Counter)
        used = 0
        for (run, tail), count in run_counts.items():
            anchors = [(pos, resolved[g]) for pos, g in enumerate(run) if g in resolved]
            if not anchors or len(anchors) == len(run):
                continue
            sets = [position_index.get((len(run), pos, ch), set()) for pos, ch in anchors]
            candidates = set.intersection(*sets) if sets else set()
            if not candidates:
                continue
            best, best_score = None, None
            for word in candidates:
                if any(c not in char_pos for c in word):
                    continue
                value = sum(float(scores[g, char_pos[c]]) for g, c in zip(run, word))
                if tail and word in tails:
                    if any(tail.startswith(t) for t in tails[word]):
                        value += 1.0
                if best_score is None or value > best_score:
                    best, best_score = word, value
            if best is None:
                continue
            used += 1
            for glyph, ch in zip(run, best):
                if glyph not in resolved:
                    votes[glyph][ch] += count

        added = 0
        for glyph, counter in votes.items():
            top_char, top_count = counter.most_common(1)[0]
            if top_count >= 2 and top_count / sum(counter.values()) >= 0.6:
                resolved[glyph] = top_char
                added += 1
        print(f"round {round_no + 1}: {used} runs used, {added} new glyphs, "
              f"{len(resolved)} resolved total")
        if not added:
            break

    hits = total = 0
    for glyph, expected in sorted(KNOWN.items()):
        if glyph in resolved:
            total += 1
            hits += resolved[glyph] == expected
            mark = "ok  " if resolved[glyph] == expected else "MISS"
            print(f"   {mark} glyph {glyph:4d} expect {expected} got {resolved[glyph]}")
    print(f"known-glyph check: {hits}/{total}")

    out_table = []
    context_new = 0
    for entry in table:
        glyph = entry["index"]
        if entry["source"] != "bitmap":
            out_table.append(entry)
            continue
        if glyph in resolved:
            context_new += 1
            out_table.append({"index": glyph, "char": resolved[glyph], "source": "context",
                              "confidence": "medium", "alts": entry.get("alts", [])})
        else:
            out_table.append(entry)
    args.out.write_text(json.dumps(out_table, ensure_ascii=False, indent=1), encoding="utf-8")
    tiers = Counter((e["source"], e["confidence"]) for e in out_table)
    print(f"\n{context_new} previously bitmap-only glyphs resolved from context")
    print(f"table -> {args.out}")
    for key, n in sorted(tiers.items()):
        print(f"   {key[0]:8s} {key[1]:8s} {n}")


if __name__ == "__main__":
    main()

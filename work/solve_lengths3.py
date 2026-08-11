"""Third attempt at the instruction-length table, using marker-anchored text blocks.

The earlier solvers located text by looking for text-shaped bytes, which also matches
operand data that happens to fall in the kana range.  Every one of those false blocks
made the walker step over real instructions and desynchronise, which is why it settled
on nonsense like a length for 0xFF.

Here text comes from the `07 1C` / `12 10` markers instead — 8,852 occurrences, none of
them inside text — so block edges are exact.  With trustworthy anchors, a length is
accepted only when it never steps over a known boundary anywhere in the stream.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import text_blocks
from text_blocks import TEXT_START

SEED = {(0x00,): 1, (0x01,): 5, (0x0E,): 5, (0x14,): 1}
TWO_BYTE = {0x09, 0x12, 0x13, 0x07, 0x17, 0x1C, 0x0F, 0x16}
MAX_DIRECT_GAP = 12


def key_for(plain: bytes, pos: int) -> tuple:
    if plain[pos] in TWO_BYTE and pos + 1 < len(plain):
        return (plain[pos], plain[pos + 1])
    return (plain[pos],)


def walk(plain, blocks, lengths, start, stop, known):
    """Step from start to stop; report where it stopped and boundaries stepped over."""
    pos = start
    violations = 0
    n = min(len(plain), stop)
    while pos < n:
        step = blocks.get(pos)
        if step is None:
            step = lengths.get(key_for(plain, pos))
            if step is None:
                return pos, violations
        for inner in range(pos + 1, min(pos + step, n)):
            if inner in known:
                violations += 1
                break
        pos += step
    return pos, violations


def evaluate(plain, blocks, lengths, ordered, known):
    reach = violations = 0
    blocked: Counter = Counter()
    for index, start in enumerate(ordered):
        stop = ordered[index + 1] if index + 1 < len(ordered) else len(plain)
        pos, bad = walk(plain, blocks, lengths, start, stop, known)
        reach += pos - start
        violations += bad
        if pos < stop and pos not in blocks:
            blocked[key_for(plain, pos)] += 1
    return reach, violations, blocked


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=60)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    plain = text_blocks.load_stream()
    found = text_blocks.find_blocks(plain)
    blocks = text_blocks.text_map(found)
    known = text_blocks.boundaries(found)
    ordered = sorted(known)
    total = len(plain) - TEXT_START
    print(f"{len(found)} text blocks, {len(known)} certain boundaries")

    lengths = dict(SEED)

    direct: dict[tuple, Counter] = defaultdict(Counter)
    for index in range(len(ordered) - 1):
        a, b = ordered[index], ordered[index + 1]
        if a in blocks or not (1 <= b - a <= MAX_DIRECT_GAP):
            continue
        direct[key_for(plain, a)][b - a] += 1

    reach, violations, blocked = evaluate(plain, blocks, lengths, ordered, known)
    print(f"start: walked {reach * 100 / total:.1f}%, {violations} violations, "
          f"{len(blocked)} keys blocking")

    for round_no in range(args.rounds):
        if not blocked:
            break
        best = None
        for key, _ in blocked.most_common(5):
            options = direct.get(key)
            candidates = [c for c, _ in options.most_common(4)] if options else list(range(1, 10))
            for candidate in candidates:
                trial = dict(lengths)
                trial[key] = candidate
                r, v, _ = evaluate(plain, blocks, trial, ordered, known)
                if v > violations:          # never accept new violations
                    continue
                if best is None or r > best[0]:
                    best = (r, v, key, candidate)
        if best is None or best[0] <= reach:
            print("   no candidate improves coverage without adding violations")
            break
        reach, violations, key, candidate = best
        lengths[key] = candidate
        _, _, blocked = evaluate(plain, blocks, lengths, ordered, known)
        pretty = " ".join(f"{b:02x}" for b in key)
        print(f"round {round_no + 1}: {pretty} -> {candidate}   walked {reach * 100 / total:.1f}%, "
              f"{violations} violations, {len(blocked)} blocking")

    print(f"\nfinal: {len(lengths)} keys, walked {reach * 100 / total:.1f}%, "
          f"{violations} violations")
    for key in sorted(lengths):
        print("   " + " ".join(f"{b:02x}" for b in key) + f" : {lengths[key]}")
    if args.out:
        args.out.write_text(json.dumps(
            {" ".join(f"{b:02x}" for b in k): v for k, v in sorted(lengths.items())}, indent=1),
            encoding="utf-8")
        print(f"-> {args.out}")


if __name__ == "__main__":
    main()

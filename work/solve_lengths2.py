"""Second attempt at recovering the instruction-length table.

The first solver demanded zero contradictions, which no candidate could satisfy: about
1.2% of the anchor addresses are not real boundaries, and a single bad anchor vetoed
everything.  It also keyed lengths on the opcode byte alone, which cannot express the
prefixed forms visible in the stream (`13 10 …` beside `13 12 10 …`).

This version fixes both.  Short gaps between consecutive anchors are used as direct
evidence — a gap of a few bytes almost always holds exactly one instruction — keys may
include the following byte, and a candidate is judged by how much more of the stream it
lets us walk against how many boundaries it violates, rather than by a veto.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from solve_lengths import SEED, TEXT_START, anchors, load

MAX_DIRECT_GAP = 10


def key_for(plain: bytes, pos: int, two_byte: set[int]) -> tuple:
    if plain[pos] in two_byte and pos + 1 < len(plain):
        return (plain[pos], plain[pos + 1])
    return (plain[pos],)


def walk(plain, text, lengths, two_byte, start, stop, known):
    pos = start
    violations = 0
    n = min(len(plain), stop)
    while pos < n:
        if pos in text:
            step = text[pos]
        else:
            step = lengths.get(key_for(plain, pos, two_byte))
            if step is None:
                return pos, violations
        for inner in range(pos + 1, pos + step):
            if inner in known:
                violations += 1
                break
        pos += step
    return pos, violations


def evaluate(plain, text, lengths, two_byte, ordered, known):
    reach = 0
    violations = 0
    blocked: Counter = Counter()
    for index, start in enumerate(ordered):
        stop = ordered[index + 1] if index + 1 < len(ordered) else len(plain)
        pos, bad = walk(plain, text, lengths, two_byte, start, stop, known)
        reach += pos - start
        violations += bad
        if pos < stop and pos not in text:
            blocked[key_for(plain, pos, two_byte)] += 1
    return reach, violations, blocked


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=40)
    parser.add_argument("--two-byte", default="09,12,13,07,17,1c,0f,16",
                        help="opcodes whose length depends on the next byte")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    plain, text = load()
    known = anchors(plain, text)
    ordered = sorted(known)
    two_byte = {int(x, 16) for x in args.two_byte.split(",")}
    print(f"{len(text)} text runs, {len(known)} anchors, two-byte keys for "
          f"{sorted(hex(x) for x in two_byte)}")

    lengths = {(k,): v for k, v in SEED.items()}

    # direct evidence: a short gap between consecutive anchors is usually one instruction
    direct: dict[tuple, Counter] = defaultdict(Counter)
    for index in range(len(ordered) - 1):
        a, b = ordered[index], ordered[index + 1]
        if a in text or not (1 <= b - a <= MAX_DIRECT_GAP):
            continue
        direct[key_for(plain, a, two_byte)][b - a] += 1

    reach, violations, blocked = evaluate(plain, text, lengths, two_byte, ordered, known)
    total = len(plain) - TEXT_START
    print(f"start: walked {reach} of {total} ({reach * 100 / total:.1f}%), "
          f"{violations} violations, {len(blocked)} keys blocking")

    for round_no in range(args.rounds):
        if not blocked:
            break
        best = None
        for key, _ in blocked.most_common(6):
            options = direct.get(key)
            candidates = [c for c, _ in options.most_common(3)] if options else list(range(1, 9))
            for candidate in candidates:
                trial = dict(lengths)
                trial[key] = candidate
                r, v, _ = evaluate(plain, text, trial, two_byte, ordered, known)
                score = r - 200 * v
                if best is None or score > best[0]:
                    best = (score, key, candidate, r, v)
        if best is None:
            break
        score, key, candidate, r, v = best
        if r <= reach:
            print("   no candidate improves coverage; stopping")
            break
        lengths[key] = candidate
        reach, violations = r, v
        _, _, blocked = evaluate(plain, text, lengths, two_byte, ordered, known)
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

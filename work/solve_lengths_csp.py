"""Recover the instruction-length table as a constraint satisfaction problem.

The greedy solvers failed because they satisfied one gap at a time and happily invented
a length for whatever byte blocked them, drifting into operand data.  The gaps between
text blocks are far more informative taken together: each one has both endpoints fixed
and must be filled *exactly*, so with 8,821 of them the system is heavily overdetermined
and a wrong length contradicts some gap somewhere.

Each key starts with a domain of possible lengths.  For one gap, a length v is feasible
at position p only if p is reachable from the gap start and p+v can still reach the gap
end — computed by a forward and a backward sweep, which is linear rather than
exponential.  Values no gap supports are removed, and the sweep repeats until nothing
changes.  Because reachability treats each position independently it never prunes a
genuinely possible value, so the result is a sound over-approximation that shrinks to
the truth as constraints accumulate.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import text_blocks

TWO_BYTE = {0x09, 0x12, 0x13, 0x07, 0x17, 0x1C, 0x0F, 0x16}
MAX_LEN = 12
SEED = {(0x00,): {1}, (0x01,): {5}, (0x0E,): {5}, (0x14,): {1}}


def key_at(plain: bytes, pos: int) -> tuple:
    if plain[pos] in TWO_BYTE and pos + 1 < len(plain):
        return (plain[pos], plain[pos + 1])
    return (plain[pos],)


def gap_support(plain: bytes, start: int, end: int,
                domains: dict[tuple, set[int]]) -> dict[tuple, set[int]] | None:
    """Which lengths each key can take inside this gap, or None if the gap is unsolvable."""
    span = end - start
    forward = [False] * (span + 1)
    forward[0] = True
    for offset in range(span):
        if not forward[offset]:
            continue
        key = key_at(plain, start + offset)
        for value in domains.get(key, ()):
            if offset + value <= span:
                forward[offset + value] = True

    if not forward[span]:
        return None

    backward = [False] * (span + 1)
    backward[span] = True
    for offset in range(span - 1, -1, -1):
        key = key_at(plain, start + offset)
        for value in domains.get(key, ()):
            if offset + value <= span and backward[offset + value]:
                backward[offset] = True
                break

    support: dict[tuple, set[int]] = defaultdict(set)
    for offset in range(span):
        if not (forward[offset] and backward[offset]):
            continue
        key = key_at(plain, start + offset)
        for value in domains.get(key, ()):
            if offset + value <= span and backward[offset + value]:
                support[key].add(value)
    return support


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-gap", type=int, default=160)
    parser.add_argument("--rounds", type=int, default=25)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    plain = text_blocks.load_stream()
    blocks = text_blocks.find_blocks(plain)
    gaps = []
    for a, b in zip(blocks, blocks[1:]):
        if 0 < b.marker - a.end <= args.max_gap:
            gaps.append((a.end, b.marker))
    print(f"{len(blocks)} text blocks, {len(gaps)} gaps of <= {args.max_gap} bytes")

    keys = set()
    for start, end in gaps:
        for offset in range(start, end):
            keys.add(key_at(plain, offset))
    print(f"{len(keys)} distinct keys appear inside gaps")

    domains: dict[tuple, set[int]] = {k: set(SEED.get(k, range(1, MAX_LEN + 1))) for k in keys}
    for k, v in SEED.items():
        domains.setdefault(k, set(v))

    for round_no in range(args.rounds):
        support: dict[tuple, set[int]] = defaultdict(set)
        unsolvable = 0
        for start, end in gaps:
            result = gap_support(plain, start, end, domains)
            if result is None:
                unsolvable += 1
                continue
            for key, values in result.items():
                support[key] |= values

        changed = 0
        for key in list(domains):
            if key in SEED:
                continue
            if key not in support:
                continue
            narrowed = domains[key] & support[key]
            if narrowed and narrowed != domains[key]:
                domains[key] = narrowed
                changed += 1

        settled = sum(1 for v in domains.values() if len(v) == 1)
        sizes = Counter(len(v) for v in domains.values())
        print(f"round {round_no + 1}: {changed} domains narrowed, {settled}/{len(domains)} settled, "
              f"{unsolvable} gaps unsolvable, sizes {dict(sorted(sizes.items()))}")
        if not changed:
            break

    settled = {k: next(iter(v)) for k, v in domains.items() if len(v) == 1}
    print(f"\n{len(settled)} keys determined uniquely:")
    for key in sorted(settled):
        print("   " + " ".join(f"{b:02x}" for b in key) + f" : {settled[key]}")

    unsettled = {k: sorted(v) for k, v in domains.items() if len(v) > 1}
    if unsettled:
        print(f"\n{len(unsettled)} keys still ambiguous (showing 20):")
        for key in sorted(unsettled)[:20]:
            print("   " + " ".join(f"{b:02x}" for b in key) + f" : {unsettled[key]}")

    if args.out:
        args.out.write_text(json.dumps({
            "settled": {" ".join(f"{b:02x}" for b in k): v for k, v in sorted(settled.items())},
            "ambiguous": {" ".join(f"{b:02x}" for b in k): v for k, v in sorted(unsettled.items())},
        }, indent=1), encoding="utf-8")
        print(f"-> {args.out}")


if __name__ == "__main__":
    main()

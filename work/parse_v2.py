"""Parse the stream with the two-level model, and check it against the dispatch table.

    opcode byte (must be 0x00-0x1C)
    + the handler's own inline operand bytes
    + one type tag per argument the handler reads, plus that tag's payload

The check that matters is external for the first time.  The table at 0x089241D8 has no entry
above 0x1C -- past it lies the string "disc" -- so the game dies immediately on anything
higher.  A parse that walks the stream and only ever lands on 0x00-0x1C is agreeing with the
code that runs it; one that produces 0x37 or 0x88 has desynced, and says so at the exact
byte where it went wrong rather than passing quietly the way the old self-consistent checks
did.

Failures are reported with their context so the missing piece can be read off the stream
instead of guessed at.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import text_blocks

SCRIPT_START = 0x02AC80
MAX_OPCODE = 0x1C

# operand bytes a handler consumes itself, from opcode_lengths_real.py
INLINE = {0x03: 1, 0x04: 1, 0x0D: 1, 0x0F: 2, 0x10: 1, 0x15: 1, 0x1A: 4, 0x1C: 1}
# arguments each handler reads, from arg_counts.py
ARGS = {0x09: 1, 0x0C: 1, 0x0D: 1, 0x11: 1, 0x12: 1}
# payload after an argument's type tag, from the table at 0x0892442C
PAYLOAD = {**{t: 0 for t in range(0x00, 0x0F)}, 0x10: 4, 0x11: 0, 0x12: 0,
           0x13: 0, 0x14: 0, 0x15: 1, 0x16: 1}


def step(plain: bytes, pos: int) -> tuple[int, str | None]:
    op = plain[pos]
    if op > MAX_OPCODE:
        return pos, f"opcode 0x{op:02x} has no dispatch entry"
    at = pos + 1 + INLINE.get(op, 0)
    for _ in range(ARGS.get(op, 0)):
        if at >= len(plain):
            return at, "ran off the end reading an argument"
        tag = plain[at]
        if tag not in PAYLOAD:
            return at, f"argument tag 0x{tag:02x} is not in the type table"
        at += 1 + PAYLOAD[tag]
    return at, None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=lambda v: int(v, 0), default=SCRIPT_START)
    parser.add_argument("--show", type=int, default=6)
    args = parser.parse_args()

    plain = text_blocks.load_stream()
    pos, seen, ops = args.start, [], Counter()
    reason = None
    while pos < len(plain):
        seen.append(pos)
        ops[plain[pos]] += 1
        nxt, reason = step(plain, pos)
        if reason:
            break
        pos = nxt

    reached = pos - args.start
    total = len(plain) - args.start
    print(f"parsed {len(seen)} instructions covering {reached} of {total} bytes "
          f"({100.0 * reached / total:.2f}%)")
    print(f"   stopped at 0x{pos:06x}: {reason}")
    print(f"   opcodes seen: {[(f'{c:02x}', n) for c, n in ops.most_common(8)]}")

    lo = max(args.start, pos - 24)
    print(f"\n   bytes before the stop: {plain[lo:pos].hex(' ')}")
    print(f"   bytes from the stop:   {plain[pos:pos + 24].hex(' ')}")
    print(f"   last {args.show} instruction starts: "
          f"{[f'0x{p:06x}({plain[p]:02x})' for p in seen[-args.show:]]}")


if __name__ == "__main__":
    main()

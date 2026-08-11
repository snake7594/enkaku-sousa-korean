"""Derive the bytecode's instruction-length table from the stream itself.

The interpreter has no dispatch table with lengths attached, so the table is recovered
by constraint solving instead of by reading MIPS.  Two sets of positions are known to be
instruction boundaries beyond doubt:

  * the start of every text run
  * every address stored in an `01` operand (98.8% of them land on a boundary)

Starting from those anchors and the few lengths already read off the stream, walking
forward proves more boundaries, which in turn pins down more opcodes.  A candidate
length is only accepted if adopting it increases how much of the stream can be walked
without ever stepping over a known boundary — stepping over one means the length is
wrong, so that check is what keeps the solution honest.
"""

from __future__ import annotations

import argparse
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path

import lzss
from extract_all_text import TEXT_START, find_runs
from opcode_survey import _span

SRC = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR\0000")
STREAM1 = 0x27E000

SEED = {0x00: 1, 0x01: 5, 0x0E: 5, 0x14: 1}


def load():
    plain = lzss.decompress(SRC.read_bytes(), STREAM1)[0]
    runs = find_runs(plain, TEXT_START, min_tokens=3, min_wide=1)
    text = {}
    for offset, _ in runs:
        text[offset] = _span(plain, offset)
    return plain, text


def anchors(plain: bytes, text: dict[int, int]) -> set[int]:
    known = set(text)
    for offset, length in text.items():
        known.add(offset + length)
    i = TEXT_START
    n = len(plain)
    while i + 5 <= n:
        if plain[i] == 0x01 and i not in text:
            value = struct.unpack_from("<I", plain, i + 1)[0]
            if TEXT_START <= value < n:
                known.add(value)
            i += 5
            continue
        i += 1
    return {b for b in known if TEXT_START <= b < n}


def walk(plain: bytes, text: dict[int, int], lengths: dict[int, int],
         start: int, stop: int, known: set[int]) -> tuple[int, bool]:
    """Walk from `start`; return where it stopped and whether it ever skipped a boundary."""
    pos = start
    n = min(len(plain), stop)
    while pos < n:
        if pos in text:
            step = text[pos]
        else:
            step = lengths.get(plain[pos])
            if step is None:
                return pos, False
        for inner in range(pos + 1, pos + step):
            if inner in known:
                return pos, True          # stepped over a proven boundary
        pos += step
    return pos, False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=12)
    parser.add_argument("--max-len", type=int, default=12)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    plain, text = load()
    known = anchors(plain, text)
    print(f"stream 0x{len(plain):x}, {len(text)} text runs, {len(known)} anchor boundaries")

    lengths = dict(SEED)
    ordered = sorted(known)

    for round_no in range(args.rounds):
        # how far can we walk from each anchor with what we know?
        reach = 0
        stuck: Counter = Counter()
        evidence: dict[int, Counter] = defaultdict(Counter)
        for index, start in enumerate(ordered):
            stop = ordered[index + 1] if index + 1 < len(ordered) else len(plain)
            pos, skipped = walk(plain, text, lengths, start, stop, known)
            if skipped:
                continue
            reach += pos - start
            if pos < stop and pos not in text:
                op = plain[pos]
                stuck[op] += 1
                gap = stop - pos
                if 1 <= gap <= args.max_len:
                    evidence[op][gap] += 1

        print(f"round {round_no + 1}: {len(lengths)} lengths known, walked {reach} bytes, "
              f"{len(stuck)} opcodes blocking")
        if not stuck:
            break

        # adopt the best-supported length for the opcode that blocks most often
        adopted = 0
        for op, _ in stuck.most_common():
            if op in lengths or not evidence[op]:
                continue
            candidate, votes = evidence[op].most_common(1)[0]
            trial = dict(lengths)
            trial[op] = candidate
            good = bad = 0
            for index, start in enumerate(ordered):
                stop = ordered[index + 1] if index + 1 < len(ordered) else len(plain)
                _, skipped = walk(plain, text, trial, start, stop, known)
                bad += skipped
                good += not skipped
            if bad == 0:
                lengths[op] = candidate
                adopted += 1
                print(f"   opcode {op:02x} -> {candidate} bytes ({votes} spans agree)")
                break
        if not adopted:
            print("   no further opcode could be settled without contradiction")
            break

    print(f"\nfinal table ({len(lengths)} opcodes):")
    for op in sorted(lengths):
        print(f"   {op:02x}: {lengths[op]}")

    if args.out:
        args.out.write_text(json.dumps({f"{k:02x}": v for k, v in sorted(lengths.items())},
                                       indent=1), encoding="utf-8")
        print(f"-> {args.out}")


if __name__ == "__main__":
    main()

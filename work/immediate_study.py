"""Decide whether `01 <u32>` operands are constants or code addresses.

This is the crux of safe relocation.  If any of them are absolute addresses into the
script, they must be remapped when text grows, and missing one crashes the game.  Two
properties separate the cases:

  * addresses in real code are mostly distinct; enumerated constants repeat heavily
  * an address points at an instruction boundary, a constant lands anywhere

Instruction boundaries are approximated by walking forward from a known-good anchor and
recording where instructions start, using the opcode lengths established so far.
"""

from __future__ import annotations

import argparse
import struct
from collections import Counter
from pathlib import Path

import lzss
from extract_all_text import TEXT_START, find_runs
from opcode_survey import _span

SRC = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR\0000")
STREAM1 = 0x27E000

# lengths inferred from the survey; text is handled separately
LENGTHS = {0x00: 1, 0x01: 5, 0x02: 1, 0x03: 1, 0x0E: 5, 0x14: 1, 0x15: 1}
PREFIXED = {(0x09, 0x10): 6, (0x12, 0x10): 6, (0x13, 0x10): 6, (0x13, 0x12): 7}


def boundaries(plain: bytes, mask: bytearray, start: int, limit: int) -> set[int]:
    """Instruction starts reachable by walking forward from `start`."""
    out = set()
    i = start
    n = min(len(plain), limit)
    while i < n:
        out.add(i)
        if mask[i]:
            i += max(1, _span(plain, i))
            continue
        b = plain[i]
        pair = PREFIXED.get((b, plain[i + 1] if i + 1 < n else 0))
        if pair:
            i += pair
        else:
            i += LENGTHS.get(b, 1)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=lambda v: int(v, 0), default=0x80000)
    args = parser.parse_args()

    plain = lzss.decompress(SRC.read_bytes(), STREAM1)[0]
    mask = bytearray(len(plain))
    for offset, _ in find_runs(plain, TEXT_START, min_tokens=3, min_wide=1):
        for i in range(offset, min(offset + _span(plain, offset), len(plain))):
            mask[i] = 1

    values = []
    i = TEXT_START
    while i + 5 <= len(plain):
        if not mask[i] and plain[i] == 0x01:
            values.append(struct.unpack_from("<I", plain, i + 1)[0])
            i += 5
            continue
        i += 1

    counts = Counter(values)
    print(f"{len(values)} `01` operands, {len(counts)} distinct")
    big = [v for v in counts if v >= TEXT_START]
    print(f"   distinct values >= 0x{TEXT_START:x} (could be script addresses): {len(big)}")
    print(f"   distinct values below that (plainly constants): {len(counts) - len(big)}")
    print(f"   most repeated: {[(hex(v), c) for v, c in counts.most_common(5)]}")

    bounds = boundaries(plain, mask, TEXT_START, args.limit)
    testable = [v for v in big if v < args.limit]
    if testable:
        on = sum(1 for v in testable if v in bounds)
        print(f"\nof {len(testable)} candidate addresses below 0x{args.limit:x}, "
              f"{on} land on an instruction boundary ({on * 100 / len(testable):.1f}%)")
        # baseline: how often would a random offset land on a boundary?
        density = len(bounds) / (args.limit - TEXT_START)
        print(f"   boundary density is {density * 100:.1f}%, so chance alone would give "
              f"about {density * len(testable):.0f}")


if __name__ == "__main__":
    main()

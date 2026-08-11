"""Work out how `0e <s32>` computes its destination.

The relocation problem disappears if text can be replaced by a jump to a larger copy
elsewhere, but that only works if 0x0E is an unconditional relative branch and we know
what its displacement is measured from.

Both conventions are tested against the existing code: whichever one makes jump targets
land on positions we already know are instruction boundaries — text-run starts and the
addresses stored in `01` operands — is the real one.  A wrong convention would scatter
targets at random, so the difference should be stark.
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=8)
    args = parser.parse_args()

    plain = lzss.decompress(SRC.read_bytes(), STREAM1)[0]
    runs = find_runs(plain, TEXT_START, min_tokens=3, min_wide=1)

    text_start = {offset for offset, _ in runs}
    text_bytes = set()
    marker_start = set()
    for offset, _ in runs:
        for i in range(offset, offset + _span(plain, offset)):
            text_bytes.add(i)
        marker_start.add(offset - 2)
        marker_start.add(offset - 1)

    anchors = set(text_start)
    i = TEXT_START
    while i + 5 <= len(plain):
        if plain[i] == 0x01 and i not in text_bytes:
            value = struct.unpack_from("<I", plain, i + 1)[0]
            if TEXT_START <= value < len(plain):
                anchors.add(value)
            i += 5
            continue
        i += 1
    print(f"{len(anchors)} known boundaries ({len(text_start)} of them text starts)")

    sites = []
    i = TEXT_START
    while i + 5 <= len(plain):
        if plain[i] == 0x0E and i not in text_bytes:
            delta = struct.unpack_from("<i", plain, i + 1)[0]
            if -0x10000 < delta < 0x10000:
                sites.append((i, delta))
            i += 5
            continue
        i += 1
    print(f"{len(sites)} `0e` sites with a small signed operand\n")

    for label, base in (("from end of instruction (pos+5)", 5), ("from start of instruction", 0)):
        hits = Counter()
        for pos, delta in sites:
            target = pos + base + delta
            if not (TEXT_START <= target < len(plain)):
                hits["out of range"] += 1
            elif target in anchors:
                hits["known boundary"] += 1
            elif target in marker_start:
                hits["text marker"] += 1
            elif target in text_bytes:
                hits["inside text"] += 1
            else:
                hits["elsewhere"] += 1
        total = sum(hits.values())
        good = hits["known boundary"] + hits["text marker"]
        print(f"{label}: {good}/{total} land on something known ({good * 100 / total:.1f}%)")
        for kind, count in hits.most_common():
            print(f"   {kind:16s} {count:6d}")
        print()

    print("sample sites:")
    for pos, delta in sites[: args.samples]:
        print(f"   0x{pos:08x} delta {delta:+6d} -> end-based 0x{pos + 5 + delta:08x}, "
              f"start-based 0x{pos + delta:08x}")


if __name__ == "__main__":
    main()

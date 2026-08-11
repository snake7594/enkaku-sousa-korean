"""Determine how text is framed in the bytecode.

Reflow stalled because instruction lengths are unknown, but expanding text does not
actually require decoding every instruction — it requires knowing exactly where each
text block begins and ends.  Those edges are markers in the stream, and markers can be
established statistically without understanding the surrounding code at all.

`07 1c` occurs about 8,700 times against 9,626 detected runs, so it is almost certainly
the opening marker.  This measures what precedes and follows every run to pin the frame
down, and reports how consistent the pattern is — consistency is what makes it safe to
rely on.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import lzss
from extract_all_text import TEXT_START, find_runs
from opcode_survey import _span

SRC = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR\0000")
STREAM1 = 0x27E000


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=6)
    args = parser.parse_args()

    plain = lzss.decompress(SRC.read_bytes(), STREAM1)[0]
    runs = find_runs(plain, TEXT_START, min_tokens=3, min_wide=1)
    print(f"{len(runs)} text runs\n")

    before2 = Counter()
    before1 = Counter()
    after1 = Counter()
    after2 = Counter()
    spans = []
    for offset, _ in runs:
        length = _span(plain, offset)
        spans.append((offset, length))
        before2[plain[offset - 2 : offset].hex()] += 1
        before1[plain[offset - 1]] += 1
        end = offset + length
        after1[plain[end]] += 1
        after2[plain[end : end + 2].hex()] += 1

    print("two bytes immediately BEFORE each run:")
    for pattern, count in before2.most_common(8):
        print(f"   {pattern}  {count:6d}  ({count * 100 / len(runs):5.1f}%)")

    print("\ntwo bytes immediately AFTER each run:")
    for pattern, count in after2.most_common(8):
        print(f"   {pattern}  {count:6d}  ({count * 100 / len(runs):5.1f}%)")

    # how many runs are cleanly framed by the dominant pair?
    open_marker = before2.most_common(1)[0][0]
    close_marker = after2.most_common(1)[0][0]
    framed = sum(1 for offset, length in spans
                 if plain[offset - 2 : offset].hex() == open_marker
                 and plain[offset + length : offset + length + 2].hex() == close_marker)
    print(f"\nruns framed by {open_marker} ... {close_marker}: {framed}/{len(runs)} "
          f"({framed * 100 / len(runs):.1f}%)")

    # is the opening marker unambiguous?  count it everywhere outside text
    inside = bytearray(len(plain))
    for offset, length in spans:
        for i in range(offset, offset + length):
            inside[i] = 1
    raw = bytes.fromhex(open_marker)
    total = occurrences = 0
    pos = TEXT_START
    while True:
        idx = plain.find(raw, pos)
        if idx < 0:
            break
        total += 1
        if not inside[idx]:
            occurrences += 1
        pos = idx + 1
    print(f"marker {open_marker} appears {total} times, {occurrences} outside text "
          f"(runs detected: {len(runs)})")

    print("\nsample frames:")
    for offset, length in spans[: args.samples]:
        lead = plain[offset - 4 : offset].hex(" ")
        tail = plain[offset + length : offset + length + 6].hex(" ")
        print(f"   0x{offset:08x} len {length:4d}   [{lead}] TEXT [{tail}]")


if __name__ == "__main__":
    main()

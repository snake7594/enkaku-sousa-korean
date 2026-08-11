"""Assess whether text can be relocated by rewriting the bytecode's pointers.

Lines cannot grow in place because the bytecode addresses text by absolute offset, and
the Korean translation needs about 40% more room than the Japanese it replaces.  The
self-contained fix is to move text and update every pointer — which is only safe if the
pointers can be enumerated exhaustively.

`01 <u32>` is the push-pointer opcode.  This counts how many such words land on the
start of a known text run, how many land elsewhere, and whether any other 4-byte
alignment in the file also happens to hold those values (which would mean a naive
search-and-replace could corrupt unrelated data).
"""

from __future__ import annotations

import argparse
import struct
from collections import Counter
from pathlib import Path

import lzss
from extract_all_text import TEXT_START, find_runs

SRC = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR\0000")
STREAM1 = 0x27E000
PUSH_PTR = 0x01


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args()

    plain = lzss.decompress(SRC.read_bytes(), STREAM1)[0]
    size = len(plain)
    runs = find_runs(plain, TEXT_START, min_tokens=3, min_wide=1)
    starts = {offset for offset, _ in runs}
    print(f"stream 0x{size:x}, {len(runs)} text runs")

    # every 01 xx xx xx xx whose operand is a plausible in-file address
    pointers = []
    i = TEXT_START
    while i + 5 <= size:
        if plain[i] == PUSH_PTR:
            value = struct.unpack_from("<I", plain, i + 1)[0]
            if 0 < value < size:
                pointers.append((i, value))
            i += 5
            continue
        i += 1
    print(f"{len(pointers)} `01 <u32>` operands with in-file targets")

    hits = Counter()
    for _, value in pointers:
        hits["text run start" if value in starts else "elsewhere"] += 1
    print(f"   pointing at a text run start: {hits['text run start']}")
    print(f"   pointing elsewhere          : {hits['elsewhere']}")

    covered = {value for _, value in pointers if value in starts}
    print(f"   distinct runs referenced    : {len(covered)} of {len(runs)}")
    print(f"   runs with no pointer found  : {len(runs) - len(covered)}")

    # would a value-based rewrite be ambiguous?
    sample = [value for value in list(covered)[:200]]
    ambiguous = 0
    for value in sample:
        needle = struct.pack("<I", value)
        count = plain.count(needle)
        opcode_count = sum(1 for pos, v in pointers if v == value)
        if count > opcode_count:
            ambiguous += 1
    print(f"\nof {len(sample)} sampled run addresses, {ambiguous} also appear as raw bytes "
          f"outside a push-pointer opcode")
    print("   -> relocation must rewrite operands found by opcode position, not by value")


if __name__ == "__main__":
    main()

"""Determine whether the VM's control flow is relative or absolute.

This decides the whole relocation design.  If jumps store a signed displacement, then
inserting bytes only disturbs jumps whose span crosses the insertion point, and the
edit is local.  If they store absolute addresses, every one of them has to be remapped.

`0e` is the candidate: it is usually followed by 0xD1 0xFF 0xFF 0xFF, which reads as
-47 signed — small and negative, the shape of a backward branch.
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


def text_mask(plain: bytes) -> bytearray:
    mask = bytearray(len(plain))
    for offset, _ in find_runs(plain, TEXT_START, min_tokens=3, min_wide=1):
        for i in range(offset, min(offset + _span(plain, offset), len(plain))):
            mask[i] = 1
    return mask


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opcodes", default="0e,01,09,12,13")
    args = parser.parse_args()

    plain = lzss.decompress(SRC.read_bytes(), STREAM1)[0]
    mask = text_mask(plain)
    size = len(plain)

    for name in args.opcodes.split(","):
        op = int(name, 16)
        signed = Counter()
        values = []
        i = TEXT_START
        while i + 5 <= size:
            if mask[i] or plain[i] != op:
                i += 1
                continue
            raw = struct.unpack_from("<i", plain, i + 1)[0]
            values.append((i, raw))
            if -0x10000 < raw < 0x10000:
                signed["small signed (looks relative)"] += 1
            elif 0 < raw < size:
                signed["in-file address (looks absolute)"] += 1
            else:
                signed["other"] += 1
            i += 5

        total = sum(signed.values())
        if not total:
            continue
        print(f"opcode {op:02x}: {total} operands")
        for kind, count in signed.most_common():
            print(f"   {kind:34s} {count:7d}  ({count * 100 / total:.1f}%)")

        rel = [v for _, v in values if -0x10000 < v < 0x10000]
        if rel:
            print(f"   signed range {min(rel)} .. {max(rel)}")
            # a relative branch should land on a sane spot: check target stays in range
            landed = sum(1 for pos, v in values
                         if -0x10000 < v < 0x10000 and 0 <= pos + 5 + v < size)
            print(f"   targets in range when treated as relative: {landed}/{len(rel)}")
            abs_ok = sum(1 for _, v in values if 0 < v < size)
            print(f"   values that are also valid absolute offsets: {abs_ok}")
        print()


if __name__ == "__main__":
    main()

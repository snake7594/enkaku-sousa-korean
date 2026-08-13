"""Find the block structure of USRDIR/0001-0004, which are mostly not LZ11.

Scanning for LZ11 accounts for 19%, 3%, 72% and 6% of the four files, so most of what is in
them was never opened.  But the two streams that were found in 0002 sit at 0x40 and 0x3040 --
both a 0x40-byte header past a round offset -- and the file starts with sixteen bytes of hash
followed by zeros.  That is a block header, and if it repeats, the blocks are the directory.

This looks for the shape rather than assuming a stride: sixteen bytes that are not all zero,
followed by 0x30 bytes that are.
"""

from __future__ import annotations

import argparse
import collections
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR")


def headers(blob: bytes, step: int = 0x10) -> list[int]:
    found = []
    for at in range(0, len(blob) - 0x40, step):
        head = blob[at:at + 0x10]
        if head == bytes(0x10):
            continue
        if blob[at + 0x10:at + 0x40] != bytes(0x30):
            continue
        found.append(at)
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="*",
                        default=["0001", "0002", "0003", "0004", "0010", "0011"])
    parser.add_argument("--step", type=lambda v: int(v, 0), default=0x10)
    parser.add_argument("--show", type=int, default=10)
    args = parser.parse_args()

    for name in args.names:
        blob = (ROOT / name).read_bytes()
        found = headers(blob, args.step)
        print(f"=== {name}  {len(blob):,} bytes -> {len(found)} block headers")
        if not found:
            continue
        gaps = [b - a for a, b in zip(found, found[1:])]
        common = collections.Counter(gaps).most_common(4)
        print(f"    gaps: {common}")
        aligned = collections.Counter(a % 0x800 for a in found).most_common(3)
        print(f"    offset mod 0x800: {aligned}")
        for at in found[: args.show]:
            follows = blob[at + 0x40:at + 0x48]
            print(f"    {at:#09x}  hash {blob[at:at + 0x10].hex()}  then {follows.hex(' ')}")
        if len(found) > args.show:
            print(f"    ... last {found[-1]:#x}")
        print()


if __name__ == "__main__":
    main()

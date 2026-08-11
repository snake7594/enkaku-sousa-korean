"""Probe the layout of the large archives (0010/0012/0013) without decompressing them."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("--align", type=lambda v: int(v, 0), default=0x800)
    parser.add_argument("--blocks", type=int, default=40)
    args = parser.parse_args()

    path = ROOT / args.name
    size = path.stat().st_size
    print(f"{path.name}: size 0x{size:x} ({size / 1e6:.1f} MB), {size // args.align} blocks of 0x{args.align:x}")

    with path.open("rb") as fh:
        # first bytes of each aligned block, to spot a repeating chunk header
        firsts = Counter()
        lz_at_00 = lz_at_40 = 0
        positions = []
        for index in range(size // args.align):
            fh.seek(index * args.align)
            head = fh.read(0x48)
            if len(head) < 0x44:
                break
            firsts[head[0]] += 1
            if head[0] == 0x11:
                lz_at_00 += 1
                positions.append(index * args.align)
            if head[0x40] == 0x11:
                lz_at_40 += 1
                positions.append(index * args.align + 0x40)
        print(f"LZ11 magic at block+0x00: {lz_at_00}, at block+0x40: {lz_at_40}")
        print("most common first bytes:", firsts.most_common(8))

        print("\nfirst blocks:")
        for index in range(args.blocks):
            fh.seek(index * args.align)
            head = fh.read(0x50)
            if not head:
                break
            dump = " ".join(f"{b:02x}" for b in head[:16])
            dump40 = " ".join(f"{b:02x}" for b in head[0x40:0x50])
            print(f"  0x{index * args.align:08x}  {dump}   +0x40: {dump40}")


if __name__ == "__main__":
    main()

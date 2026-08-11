"""Find the script interpreter's opcode dispatch table in the PSP module.

A dispatch table is a run of consecutive words that all point into .text.  Random data
almost never does that, so a long run is a strong signal.  Interpreters usually keep an
operand-length table beside the handlers too, which is what the relocation work actually
needs, so byte arrays of small values near each candidate are reported as well.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")

TEXT_VADDR = 0x08804000
TEXT_SIZE = 0x872D0
FILE_BASE = 0x54           # file offset of TEXT_VADDR
DATA_VADDR = 0x0888C69C


def to_file(vaddr: int) -> int:
    return vaddr - TEXT_VADDR + FILE_BASE


def to_vaddr(offset: int) -> int:
    return offset - FILE_BASE + TEXT_VADDR


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-run", type=int, default=16)
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args()

    data = BOOT.read_bytes()
    lo, hi = TEXT_VADDR, TEXT_VADDR + TEXT_SIZE

    runs = []
    start = None
    length = 0
    for off in range(0, len(data) - 4, 4):
        value = struct.unpack_from("<I", data, off)[0]
        if lo <= value < hi and value % 4 == 0:
            if start is None:
                start = off
            length += 1
        else:
            if start is not None and length >= args.min_run:
                runs.append((length, start))
            start, length = None, 0
    if start is not None and length >= args.min_run:
        runs.append((length, start))

    runs.sort(reverse=True)
    print(f"{len(runs)} runs of >= {args.min_run} consecutive .text pointers\n")
    for length, off in runs[: args.top]:
        distinct = len({struct.unpack_from("<I", data, off + i * 4)[0] for i in range(length)})
        print(f"   file 0x{off:06x}  vaddr 0x{to_vaddr(off):08x}  {length:4d} entries, "
              f"{distinct} distinct")

    if not runs:
        return

    print("\nchecking each candidate for a nearby small-value byte table:")
    for length, off in runs[: args.top]:
        after = off + length * 4
        window = data[after : after + 320]
        small = sum(1 for b in window if 0 < b <= 8)
        print(f"   after 0x{off:06x}: {small}/{len(window)} bytes in 1..8"
              + ("   <== possible length table" if small > len(window) * 0.7 else ""))
        before = data[max(0, off - 320) : off]
        small_b = sum(1 for b in before if 0 < b <= 8)
        if small_b > len(before) * 0.7:
            print(f"      (and before it: {small_b}/{len(before)} in 1..8)")


if __name__ == "__main__":
    main()

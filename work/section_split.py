"""Split the stream into the regions each interpreter reads.

Two interpreters exist and no function touches both: one keeps its pointer at ctx+1160 and
dispatches through 0x089241D8, the other at ctx+17016.  Evidence from one has been used to
judge the other all session -- lengths_v3 says 0x01 is a one-byte op, while the reference
statistics say `01 <u32>` is a five-byte pointer -- and both can be right if they describe
different parts of the stream.

The header holds eight offsets, which are the obvious candidates for section boundaries, and
one region is already pinned: the emulator was sitting at 0x3763E, which is 0x5FE past
header[0].  So each region is profiled two ways -- how much of it reads as valid ctx+1160
opcodes, and how many `01 <u32>` references in it resolve -- and the two interpreters should
separate cleanly.
"""

from __future__ import annotations

import struct
from collections import Counter
from pathlib import Path

import lzss

ARCHIVE = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR\0000")
FONT_END = 0x02AC80
RUNTIME = 0x3763E
LABELS = {0x09, 0x0C, 0x13, 0x0F, 0x0E, 0x15, 0x14, 0x01}


def main() -> None:
    plain = lzss.decompress(ARCHIVE.read_bytes(), 0x27E000)[0]
    size = len(plain)
    header = [h for h in struct.unpack_from("<32I", plain, 0) if FONT_END <= h < size]
    bounds = sorted({FONT_END, *header, size})
    print(f"stream {size} bytes; boundaries from the header: "
          f"{[hex(b) for b in bounds]}\n")

    print(f"{'region':>26} {'bytes':>9} {'opcode<=1C':>11} {'01 refs':>8} {'resolve':>8}")
    for lo, hi in zip(bounds, bounds[1:]):
        chunk = plain[lo:hi]
        if not chunk:
            continue
        valid = sum(1 for b in chunk if b <= 0x1C) / len(chunk)
        ones = [i for i in range(lo, hi - 5) if plain[i] == 0x01]
        good = sum(1 for i in ones
                   if FONT_END <= int.from_bytes(plain[i + 1:i + 5], "little") < size)
        rate = good / len(ones) if ones else 0.0
        mark = "   <-- runtime pointer" if lo <= RUNTIME < hi else ""
        print(f"   0x{lo:06x}-0x{hi:06x} {hi - lo:9d} {100 * valid:10.1f}% "
              f"{len(ones):8d} {100 * rate:7.1f}%{mark}")

    # what the label-opcode share looks like per region tells the two layers apart too
    print("\nbyte profile of the two largest regions:")
    for lo, hi in sorted(zip(bounds, bounds[1:]), key=lambda r: r[1] - r[0])[-2:]:
        counts = Counter(plain[lo:hi])
        top = ", ".join(f"{b:02x}:{100 * n / (hi - lo):.0f}%"
                        for b, n in counts.most_common(6))
        print(f"   0x{lo:06x}-0x{hi:06x}  {top}")


if __name__ == "__main__":
    main()

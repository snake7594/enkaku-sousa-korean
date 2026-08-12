"""Work out the record layout of the 0001-0004 archives.

The 0000 archive's records are texture headers -- width, height, tile size, pixel format --
and reading 0001 the same way gives "512x256 tile 32x32 psm 5" against records of 32,256 and
1,056 and 2,096 bytes, which cannot all be that.  So the first word is not width there, and
the guess has to be dropped and rebuilt from what the bytes actually are.

This dumps every stream's record table with the head of each record, so the shape can be read
off instead of assumed.
"""

from __future__ import annotations

import argparse
import collections
from pathlib import Path

import lzss

ROOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR")


def streams(blob: bytes, limit: int = 8):
    """Every LZ11 stream in the file, found by trying to open each 0x11 at a 16-byte step."""
    at, found = 0, 0
    while at < len(blob) - 4 and found < limit:
        if blob[at] == 0x11:
            size = int.from_bytes(blob[at + 1:at + 4], "little")
            if 4096 <= size <= 64 << 20:
                try:
                    plain, consumed = lzss.decompress(blob, at, limit=64 << 20)
                except Exception:
                    plain = None
                if plain is not None and len(plain) == size:
                    found += 1
                    yield at, plain
                    at += max(consumed, 16)
                    continue
        at += 16


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="*", default=["0001", "0002", "0003", "0004"])
    parser.add_argument("--records", type=int, default=6)
    args = parser.parse_args()

    for name in args.names:
        blob = (ROOT / name).read_bytes()
        print(f"=== {name}  {len(blob):,} bytes")
        for offset, plain in streams(blob):
            count = int.from_bytes(plain[0:4], "little")
            print(f"  stream @{offset:#x}  plain {len(plain):,}  first word {count}")
            if not 1 <= count < 4096:
                print(f"     first word is not a count; head {plain[:32].hex(' ')}")
                continue
            table = [int.from_bytes(plain[4 + i * 4:8 + i * 4], "little")
                     for i in range(count)]
            ok = all(0 < t <= len(plain) for t in table) and table == sorted(table)
            print(f"     {count} offsets, ascending and in range: {ok}")
            ends = table[1:] + [len(plain)]
            sizes = [b - a for a, b in zip(table, ends)]
            print(f"     sizes: min {min(sizes)} max {max(sizes)} "
                  f"common {collections.Counter(sizes).most_common(3)}")
            for i in range(min(args.records, count)):
                head = plain[table[i]:table[i] + 24]
                print(f"     rec{i:<3d} @{table[i]:#08x} {sizes[i]:>8d}B  {head.hex(' ')}")
            print()


if __name__ == "__main__":
    main()

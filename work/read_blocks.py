"""Open USRDIR/0001-0004 by their blocks instead of by scanning for LZ11.

Scanning found 3% of 0002 and 6% of 0004, which was never a property of the files -- it was
the scan.  These archives are a run of blocks, each starting on a 0x800 boundary with a
0x40-byte header (sixteen bytes of hash, then zeros) and holding one LZ11 stream padded out to
the next boundary.  A scan that decompresses one stream and jumps by its packed length lands
in the middle of the padding and loses the rest.

Walking the boundaries instead finds every stream, because the layout says where they are
rather than the bytes having to advertise it.
"""

from __future__ import annotations

import argparse
import collections
from pathlib import Path

import lzss

ROOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR")
BLOCK = 0x800
HEADER = 0x40


def blocks(blob: bytes):
    """Yield (offset, payload) for every 0x800-aligned block that carries a header."""
    for at in range(0, len(blob) - HEADER, BLOCK):
        if blob[at:at + 0x10] == bytes(0x10):
            continue
        if blob[at + 0x10:at + HEADER] != bytes(0x30):
            continue
        yield at, blob[at + HEADER:]


def open_stream(payload: bytes):
    if not payload or payload[0] != 0x11:
        return None, payload[:4]
    size = int.from_bytes(payload[1:4], "little")
    if not 16 <= size <= 64 << 20:
        return None, payload[:4]
    try:
        plain, _ = lzss.decompress(payload, 0, limit=64 << 20)
    except Exception:
        return None, payload[:4]
    return (plain if len(plain) == size else None), payload[:4]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="*",
                        default=["0001", "0002", "0003", "0004", "0010", "0011"])
    args = parser.parse_args()

    for name in args.names:
        blob = (ROOT / name).read_bytes()
        found = opened = 0
        magic = collections.Counter()
        plain_total = 0
        for at, payload in blocks(blob):
            found += 1
            plain, head = open_stream(payload)
            magic[bytes(head[:4]).hex(" ") if plain is None else "LZ11"] += 1
            if plain is not None:
                opened += 1
                plain_total += len(plain)
        print(f"{name}: {found} blocks, {opened} open as LZ11 "
              f"-> {plain_total:,} bytes")
        for what, n in magic.most_common(6):
            print(f"    {what}: {n}")
        print()


if __name__ == "__main__":
    main()

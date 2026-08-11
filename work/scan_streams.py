"""Scan the USRDIR archives for embedded LZ11 streams and map the container layout."""

from __future__ import annotations

import argparse
from pathlib import Path

import lzss

ROOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR")


def scan(path: Path, align: int = 0x800, max_hits: int | None = None):
    data = path.read_bytes()
    hits = []
    for off in range(0, len(data) - 8, align):
        for delta in (0x00, 0x40):
            pos = off + delta
            if pos + 8 > len(data):
                continue
            if data[pos] != 0x11:
                continue
            declared = int.from_bytes(data[pos + 1 : pos + 4], "little")
            if not (0x100 <= declared <= 0x2000000):
                continue
            result = lzss.try_decompress(data, pos, limit=0x2000000)
            if result is None:
                continue
            plain, consumed = result
            hits.append((pos, consumed, len(plain), plain[:16]))
            if max_hits and len(hits) >= max_hits:
                return data, hits
    return data, hits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*", default=None)
    parser.add_argument("--max", type=int, default=8)
    args = parser.parse_args()

    names = args.names or ["0000", "0001", "0002", "0003", "0004", "0011"]
    for name in names:
        path = ROOT / name
        data, hits = scan(path, max_hits=args.max)
        print(f"== {name} size=0x{len(data):x}  valid LZ11 streams found: {len(hits)}")
        for pos, consumed, plain_len, preview in hits:
            head = " ".join(f"{b:02x}" for b in preview)
            print(f"   @0x{pos:08x} packed=0x{consumed:<8x} plain=0x{plain_len:<8x} start[{head}]")
        print()


if __name__ == "__main__":
    main()

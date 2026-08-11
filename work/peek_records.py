"""Hexdump selected records of a decompressed stream."""

from __future__ import annotations

import argparse
from pathlib import Path

import texpack


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stream", type=Path)
    parser.add_argument("--records", type=int, nargs="*", default=None)
    parser.add_argument("--bytes", type=int, default=128)
    args = parser.parse_args()

    records = texpack.load_records(args.stream.read_bytes())
    print(f"{args.stream.name}: {len(records)} records {[hex(len(r)) for r in records]}")
    wanted = args.records if args.records is not None else range(len(records))
    for index in wanted:
        if index >= len(records):
            continue
        rec = records[index]
        print(f"\n-- record {index}  size=0x{len(rec):x}")
        for offset in range(0, min(len(rec), args.bytes), 32):
            chunk = rec[offset : offset + 32]
            hexpart = " ".join(f"{b:02x}" for b in chunk)
            text = "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in chunk)
            print(f"   {offset:04x}  {hexpart:<95s} {text}")


if __name__ == "__main__":
    main()

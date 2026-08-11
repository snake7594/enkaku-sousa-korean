"""Dump the record layout and metadata record of the first stream of each archive."""

from __future__ import annotations

import sys
from pathlib import Path

import texpack

DUMP = Path(r"D:\psp\원격수사\dump")


def main() -> None:
    names = sys.argv[1:] or ["0001", "0002", "0003"]
    for name in names:
        streams = sorted((DUMP / name).glob("*.bin"))
        if not streams:
            print(f"== {name}: no streams")
            continue
        path = streams[0]
        data = path.read_bytes()
        records = texpack.load_records(data)
        print(f"== {name} {path.name} len=0x{len(data):x} records={len(records)}")
        print("   record sizes:", [hex(len(r)) for r in records[:10]])
        meta = records[0]
        for offset in range(0, min(len(meta), 160), 32):
            print(f"   {offset:04x}  " + " ".join(f"{b:02x}" for b in meta[offset : offset + 32]))
        print()


if __name__ == "__main__":
    main()

"""Dump the 원격수사 ISO's directory tree and extract every file to disk."""

from __future__ import annotations

import argparse
from pathlib import Path

from iso9660 import BLOCK, list_records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("iso", type=Path)
    parser.add_argument("--out", type=Path, default=None, help="extract files here")
    args = parser.parse_args()

    iso = args.iso.read_bytes()
    records = list_records(iso)

    for record in sorted(records, key=lambda r: r.name):
        kind = "DIR " if record.flags & 2 else "FILE"
        print(f"{kind} {record.name:<48} lba={record.extent:<8} size={record.size}")

    if args.out is None:
        return

    for record in records:
        target = args.out / record.name.lstrip("/")
        if record.flags & 2:
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        start = record.extent * BLOCK
        target.write_bytes(iso[start : start + record.size])
    print(f"\nextracted to {args.out}")


if __name__ == "__main__":
    main()

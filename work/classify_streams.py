"""Classify every dumped stream: texture pack, tiled image, script bytecode, or unknown."""

from __future__ import annotations

import argparse
import struct
from collections import Counter
from pathlib import Path

import texpack
from tile_headers import parse_header

DUMP = Path(r"D:\psp\원격수사\dump")


def classify(data: bytes) -> tuple[str, str]:
    try:
        records = texpack.load_records(data)
    except Exception:  # noqa: BLE001
        return "unparsed", ""
    if not records:
        return "empty", ""
    shapes = [hex(len(r)) for r in records[:6]]
    for rec in records[1:]:
        parsed = parse_header(rec)
        if parsed and parsed[-1] == len(rec):
            width, height, tile_w, tile_h, psm, _flags, count, _ = parsed
            return "tiled-image", f"{width}x{height} {tile_w}x{tile_h} {texpack.PSM_NAMES[psm]} tiles={count}"
    # plain palette/image pairs (the 0000 style)
    if len(records) >= 3 and len(records[1]) in (0x40, 0x400):
        return "palette-pairs", f"{len(records)} records {shapes}"
    return "other", f"{len(records)} records {shapes}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+")
    parser.add_argument("--list-other", action="store_true")
    args = parser.parse_args()

    for name in args.archives:
        kinds = Counter()
        others = []
        for stream in sorted((DUMP / name).glob("*.bin")):
            kind, detail = classify(stream.read_bytes())
            kinds[kind] += 1
            if kind in ("other", "unparsed", "empty"):
                others.append((stream.name, stream.stat().st_size, detail))
        print(f"== {name}: {kinds.most_common()}")
        if args.list_other:
            for filename, size, detail in others[:40]:
                print(f"   {filename}  0x{size:x}  {detail}")
        print()


if __name__ == "__main__":
    main()

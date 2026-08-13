"""Tabulate what the block streams of 0001-0004 hold, now that they all open.

329 streams in 0001 alone, and the point is to find one picture -- the title screen's
`STARTボタンを押してください`.  Listing every record's header first says which streams are
pictures and what size, so only the plausible ones have to be drawn and looked at.
"""

from __future__ import annotations

import argparse
import collections
import json
import struct
from pathlib import Path

import read_blocks
import texpack


def records_of(plain: bytes):
    first = int.from_bytes(plain[0:4], "little")
    if not 8 <= first <= min(0x4000, len(plain)) or first % 4:
        return None
    try:
        return texpack.load_records(plain)
    except Exception:
        return None


def image_header(record: bytes):
    if len(record) < 16:
        return None
    width, height, tile_w, tile_h, psm, flag = struct.unpack_from("<6H", record, 0)
    start, = struct.unpack_from("<I", record, 12)
    if not (0 < width <= 4096 and 0 < height <= 4096) or psm not in (4, 5):
        return None
    if not 16 <= start < len(record):
        return None
    return dict(width=width, height=height, tile=[tile_w, tile_h], psm=psm,
                flag=flag, start=start, bytes=len(record) - start)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="*", default=["0001", "0002", "0003", "0004"])
    parser.add_argument("--out", type=Path,
                        default=Path(r"D:\psp\원격수사\build\block_survey.json"))
    args = parser.parse_args()

    catalogue, sizes, shapes = [], collections.Counter(), collections.Counter()
    for name in args.names:
        blob = (read_blocks.ROOT / name).read_bytes()
        for at, payload in read_blocks.blocks(blob):
            plain, _ = read_blocks.open_stream(payload)
            if plain is None:
                continue
            records = records_of(plain)
            if records is None:
                shapes["no record table"] += 1
                continue
            images = []
            for n, record in enumerate(records):
                header = image_header(record)
                if header:
                    images.append({"record": n, **header})
            shapes[f"{len(records)} records, {len(images)} images"] += 1
            for image in images:
                sizes[(image["width"], image["height"], image["psm"])] += 1
            catalogue.append({"file": name, "block": at, "plain": len(plain),
                              "records": [len(r) for r in records], "images": images})

    args.out.write_text(json.dumps({"schema": "enkaku_block_survey_v1",
                                    "streams": catalogue}, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"{len(catalogue)} streams with a record table")
    print("\nstream shapes:")
    for what, n in shapes.most_common(10):
        print(f"   {n:>4d}  {what}")
    print("\nimage sizes:")
    for (w, h, psm), n in sizes.most_common(20):
        print(f"   {n:>4d}  {w}x{h} psm{psm}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

"""Tabulate the tiled-image headers found across every dumped stream.

Image record layout (little endian):

    u16 width, u16 height          full image size in pixels
    u16 tile_w, u16 tile_h         tile size in pixels
    u16 psm, u16 flags             psm 4 = T4, 5 = T8
    u32 tile_count
    then tile_count * (16 byte tile entry + tile_w*tile_h*bpp/8 pixel bytes)
"""

from __future__ import annotations

import argparse
import struct
from collections import Counter
from pathlib import Path

import texpack

DUMP = Path(r"D:\psp\원격수사\dump")


def parse_header(rec: bytes):
    if len(rec) < 16:
        return None
    width, height, tile_w, tile_h, psm, flags = struct.unpack_from("<6H", rec, 0)
    count = struct.unpack_from("<I", rec, 12)[0]
    if not (0 < width <= 4096 and 0 < height <= 4096):
        return None
    if tile_w not in (8, 16, 32, 64, 128) or tile_h not in (8, 16, 32, 64, 128):
        return None
    if psm not in (0, 1, 2, 3, 4, 5):
        return None
    bpp = {4: 4, 5: 8}.get(psm)
    if bpp is None:
        return None
    tile_bytes = tile_w * tile_h * bpp // 8
    expected = 16 + count * (16 + tile_bytes)
    return width, height, tile_w, tile_h, psm, flags, count, expected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+")
    parser.add_argument("--show-mismatch", action="store_true")
    args = parser.parse_args()

    for name in args.archives:
        shapes = Counter()
        tiles = Counter()
        matched = mismatched = 0
        examples: dict[tuple, str] = {}
        for stream in sorted((DUMP / name).glob("*.bin")):
            try:
                records = texpack.load_records(stream.read_bytes())
            except Exception:  # noqa: BLE001
                continue
            for index, rec in enumerate(records):
                parsed = parse_header(rec)
                if parsed is None:
                    continue
                width, height, tile_w, tile_h, psm, flags, count, expected = parsed
                key = (width, height, tile_w, tile_h, psm)
                if expected == len(rec):
                    matched += 1
                    shapes[key] += 1
                    tiles[(tile_w, tile_h)] += 1
                    examples.setdefault(key, f"{stream.name}#r{index}")
                else:
                    mismatched += 1
                    if args.show_mismatch:
                        print(f"   ?? {stream.name}#r{index} {key} count={count} "
                              f"expected=0x{expected:x} actual=0x{len(rec):x}")

        print(f"== {name}: {matched} tiled images parsed cleanly, {mismatched} header-like but mismatched")
        print(f"   tile sizes: {tiles.most_common()}")
        for key, n in shapes.most_common(14):
            width, height, tile_w, tile_h, psm = key
            print(f"   {width:4d}x{height:<4d} tiles {tile_w}x{tile_h} {texpack.PSM_NAMES[psm]:<3s}"
                  f"  n={n:<5d} e.g. {examples[key]}")
        print()


if __name__ == "__main__":
    main()

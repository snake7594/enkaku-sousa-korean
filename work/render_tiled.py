"""Reassemble a tiled image record into the full picture.

Record layout:
    0x00 u16 width, u16 height, u16 tile_w, u16 tile_h, u16 psm, u16 flags, u32 tile_count
    0x10 per tile: 16-byte entry (u16 x, u16 y, ...) followed by tile_w*tile_h*bpp/8 pixels,
         swizzled in 16x8 byte blocks.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

import numpy as np
from PIL import Image

import texpack


def render(record: bytes, palette: bytes) -> tuple[Image.Image, list[tuple[int, int]]]:
    width, height, tile_w, tile_h, psm, flags, = struct.unpack_from("<6H", record, 0)
    count = struct.unpack_from("<I", record, 12)[0]
    bpp = {4: 4, 5: 8}[psm]
    tile_bytes = tile_w * tile_h * bpp // 8
    byte_width = tile_w * bpp // 8

    canvas = np.zeros((height, width), dtype=np.uint8)
    placements = []
    pos = 0x10
    for _ in range(count):
        entry = record[pos : pos + 16]
        pos += 16
        tx, ty = struct.unpack_from("<2H", entry, 0)
        pixels = record[pos : pos + tile_bytes]
        pos += tile_bytes
        buf = np.frombuffer(pixels, dtype=np.uint8)
        plane = texpack.unswizzle(buf, byte_width, tile_h)
        if bpp == 4:
            tile = np.empty((tile_h, tile_w), dtype=np.uint8)
            tile[:, 0::2] = plane & 0x0F
            tile[:, 1::2] = plane >> 4
        else:
            tile = plane
        x, y = tx * tile_w, ty * tile_h
        if y + tile_h <= height and x + tile_w <= width:
            canvas[y : y + tile_h, x : x + tile_w] = tile
            placements.append((tx, ty))

    colours = np.frombuffer(palette, dtype=np.uint8).reshape(-1, 4)
    if colours.shape[0] < 256:
        colours = np.vstack([colours, np.zeros((256 - colours.shape[0], 4), dtype=np.uint8)])
    return Image.fromarray(colours[canvas], "RGBA"), placements


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stream", type=Path)
    parser.add_argument("--record", type=int, default=2)
    parser.add_argument("--pal", type=int, default=1)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    records = texpack.load_records(args.stream.read_bytes())
    image, placements = render(records[args.record], records[args.pal])
    image.save(args.out)
    print(f"{image.size[0]}x{image.size[1]}, {len(placements)} tiles placed -> {args.out}")
    print(f"tile grid positions: {placements[:40]}")


if __name__ == "__main__":
    main()

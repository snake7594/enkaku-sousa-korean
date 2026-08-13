"""Decode the images in USRDIR/0001-0004.

0000 keeps texture metadata in a separate record 0 and stores its pixels bare.  These archives
do not.  Each image record carries its own header,

    u16 width, u16 height, u16 tile_w, u16 tile_h, u16 psm, u16 flag, u32 tile_count

and the pixels after it are not a continuous run.  From offset 16 they are **tiles with their
own headers**:

    u16 tile_x, u16 tile_y, 12 bytes reserved, then tile_w x tile_h bytes, 16x8 block swizzled

which is why every arrangement of a continuous run came out torn -- sixteen bytes of header
were being drawn as pixels at the head of every tile, shifting the rest.  Each tile carries
its own position, so an image can leave its empty tiles out: a 512x256 that would need 128
tiles usually stores 120, and the gaps are transparent.

The word at offset 12 reads like an offset and is not one -- it is the tile count, which is
what makes the arithmetic close exactly:

    banner    16 + 16 x 1040 = 16,656 = the record's length
    scene     16 + 120 x 1040 = 124,816
    512x512   16 + 240 x 1040 = 249,616

Reading a banner confirms the rest: `尋問開始` comes out clean.

The whole archive has to be walked by its blocks (see read_blocks.py) rather than by scanning
for LZ11, or most of the streams are never seen.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

import numpy as np
from PIL import Image

import read_blocks
import texpack

ROOT = read_blocks.ROOT
TILE_HEADER = 0x10


def records_of(plain: bytes):
    first = int.from_bytes(plain[0:4], "little")
    if not 8 <= first <= min(0x4000, len(plain)) or first % 4:
        return None
    try:
        records = texpack.load_records(plain)
    except Exception:
        return None
    return records if len(records) >= 3 else None


def decode_record(palette: bytes, record: bytes):
    """Return (image, header) for one image record, or (None, header) if it is not one."""
    if len(record) < 16:
        return None, None
    width, height, tile_w, tile_h, psm, flag = struct.unpack_from("<6H", record, 0)
    count, = struct.unpack_from("<I", record, 12)
    header = dict(width=width, height=height, tile=(tile_w, tile_h), psm=psm,
                  flag=flag, tiles=count)
    if psm not in (4, 5) or not (0 < width <= 4096 and 0 < height <= 4096):
        return None, header
    if not (0 < tile_w <= width and 0 < tile_h <= height) or width % tile_w or height % tile_h:
        return None, header

    bytes_per_row = tile_w // 2 if psm == 4 else tile_w
    stride = TILE_HEADER + bytes_per_row * tile_h
    plane_width = width // 2 if psm == 4 else width
    header["tiles_full"] = (width // tile_w) * (height // tile_h)
    if count < 1 or TILE_HEADER + count * stride > len(record):
        return None, header
    plane = np.zeros((height, plane_width), dtype=np.uint8)

    body = record[TILE_HEADER:]
    for n in range(count):
        at = n * stride
        # The tile says where it goes: two u16 holding its column and row in the tile grid.
        # That is what lets an image leave its empty tiles out and still land correctly.
        col, row = struct.unpack_from("<2H", body, at)
        if row * tile_h >= height or col * tile_w >= width:
            continue
        cell = np.frombuffer(body[at + TILE_HEADER:at + stride], dtype=np.uint8)
        plane[row * tile_h:(row + 1) * tile_h,
              col * bytes_per_row:(col + 1) * bytes_per_row] = \
            texpack.unswizzle(cell, bytes_per_row, tile_h)

    if psm == 4:
        indices = np.empty((height, width), dtype=np.uint8)
        indices[:, 0::2] = plane & 0x0F
        indices[:, 1::2] = plane >> 4
    else:
        indices = plane
    colours = np.frombuffer(palette, dtype=np.uint8)
    colours = colours[: (len(colours) // 4) * 4].reshape(-1, 4)
    if colours.shape[0] < 256:
        colours = np.vstack([colours, np.zeros((256 - colours.shape[0], 4), np.uint8)])
    return Image.fromarray(colours[indices], "RGBA"), header


def decode_stream(plain: bytes):
    """Every image in one stream, as (record index, image, header)."""
    records = records_of(plain)
    if records is None:
        return []
    out = []
    for n in range(2, len(records), 2):
        image, header = decode_record(records[n - 1], records[n])
        if image is not None:
            out.append((n, image, header))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="*", default=["0001", "0002", "0003", "0004"])
    parser.add_argument("--out", type=Path, default=Path(r"D:\psp\원격수사\build\containers"))
    parser.add_argument("--max-width", type=int, default=0,
                        help="only save images this wide or narrower (0 = all)")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    total = 0
    for name in args.names:
        blob = (ROOT / name).read_bytes()
        made = 0
        for at, payload in read_blocks.blocks(blob):
            plain, _ = read_blocks.open_stream(payload)
            if plain is None:
                continue
            for n, image, header in decode_stream(plain):
                if args.max_width and image.width > args.max_width:
                    continue
                image.save(args.out / f"{name}_{at:07x}_{n}_{image.width}x{image.height}.png")
                made += 1
        total += made
        print(f"{name}: {made} images")
    print(f"{total} images -> {args.out}")


if __name__ == "__main__":
    main()

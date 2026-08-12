"""Decode the images in USRDIR/0001-0004, whose records carry their own header.

0000 keeps texture metadata in a separate record 0 and stores the pixels bare.  These archives
do not: each image record starts with its own twelve-byte header and the pixels follow at the
offset in it.  Reading them the 0000 way produced "512x256 tile 32x32 psm 5" for records of
1,056 and 2,096 bytes, which is what a wrong reading looks like.

    u16 width, u16 height, u16 tile_w, u16 tile_h, u16 psm, u16 flag, u32 pixel_start

Each stream holds one image and its palette.  The pixel run is often shorter than width*height
-- the tail is transparent and simply not stored -- so the missing rows are filled in as empty
rather than treated as a failure.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

import numpy as np
from PIL import Image

import lzss
import texpack

ROOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR")


def streams(blob: bytes, limit: int = 512):
    at, found = 0, 0
    while at < len(blob) - 4 and found < limit:
        if blob[at] == 0x11:
            size = int.from_bytes(blob[at + 1:at + 4], "little")
            if 4096 <= size <= 64 << 20:
                try:
                    plain, consumed = lzss.decompress(blob, at, limit=64 << 20)
                except Exception:
                    plain = None
                if plain is not None and len(plain) == size:
                    found += 1
                    yield at, plain
                    at += max(consumed, 4)
                    continue
        at += 4


def detile(buf: np.ndarray, byte_width: int, height: int,
           tile_bytes: int, tile_rows: int) -> np.ndarray:
    """Lay tiles back into a picture, unswizzling inside each one.

    The header carries a tile size and it means it: the pixels are stored one 32x32 tile after
    another, left to right and top to bottom, not as continuous scanlines.  Treating the run as
    scanlines is what produced the striped mess -- every tile boundary became a horizontal tear.
    Inside a tile the usual 16x8 block swizzle still applies.
    """
    if tile_bytes <= 0 or tile_rows <= 0 or byte_width % tile_bytes or height % tile_rows:
        return texpack.unswizzle(buf, byte_width, height)
    across, down = byte_width // tile_bytes, height // tile_rows
    tiles = buf.reshape(down * across, tile_rows * tile_bytes)
    plane = np.empty((height, byte_width), dtype=np.uint8)
    for n in range(down * across):
        row, col = divmod(n, across)
        plane[row * tile_rows:(row + 1) * tile_rows,
              col * tile_bytes:(col + 1) * tile_bytes] = \
            (texpack.unswizzle(tiles[n], tile_bytes, tile_rows) if swizzled
             else tiles[n].reshape(tile_rows, tile_bytes))
    return plane


def decode_stream(plain: bytes):
    """Return (image, header) for a stream, or (None, header) when it is not a picture."""
    first = int.from_bytes(plain[0:4], "little")
    if not 8 <= first <= min(0x4000, len(plain)) or first % 4:
        return None, None                        # not a record table; some streams are data
    records = texpack.load_records(plain)
    if len(records) < 3 or len(records[2]) < 16:
        return None, None
    width, height, tile_w, tile_h, psm, flag = struct.unpack_from("<6H", records[2], 0)
    start, = struct.unpack_from("<I", records[2], 12)
    header = dict(width=width, height=height, tile=(tile_w, tile_h), psm=psm,
                  flag=flag, start=start, palette=len(records[1]), pixels=len(records[2]) - start)
    if psm not in (4, 5) or not (0 < width <= 4096 and 0 < height <= 4096):
        return None, header

    byte_width = width // 2 if psm == 4 else width
    raw = records[2][start:]
    need = byte_width * height
    if len(raw) < need:
        raw = raw + bytes(need - len(raw))       # the transparent tail is not stored
    plane = detile(np.frombuffer(raw[:need], dtype=np.uint8),
                   byte_width, height,
                   tile_w // 2 if psm == 4 else tile_w, tile_h)

    if psm == 4:
        indices = np.empty((height, width), dtype=np.uint8)
        indices[:, 0::2] = plane & 0x0F
        indices[:, 1::2] = plane >> 4
    else:
        indices = plane
    colours = np.frombuffer(records[1], dtype=np.uint8)
    colours = colours[: (len(colours) // 4) * 4].reshape(-1, 4)
    if colours.shape[0] < 256:
        colours = np.vstack([colours, np.zeros((256 - colours.shape[0], 4), np.uint8)])
    return Image.fromarray(colours[indices], "RGBA"), header


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="*", default=["0001", "0002", "0003", "0004"])
    parser.add_argument("--out", type=Path, default=Path(r"D:\psp\원격수사\build\containers"))
    parser.add_argument("--limit", type=int, default=512)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    for name in args.names:
        blob = (ROOT / name).read_bytes()
        made = skipped = 0
        for offset, plain in streams(blob, args.limit):
            image, header = decode_stream(plain)
            if image is None:
                skipped += 1
                continue
            image.save(args.out / f"{name}_{offset:08x}.png")
            made += 1
            print(f"  {name}@{offset:#09x}  {header['width']}x{header['height']} "
                  f"psm{header['psm']} tile{header['tile']} "
                  f"pixels {header['pixels']}/{header['width'] * header['height']}")
        print(f"{name}: {made} images, {skipped} streams that are not pictures\n")


if __name__ == "__main__":
    main()

"""Decode an image record from 0001-0003, which carry their dimensions inside the record.

stream0 keeps every texture's width, height and pixel format in a table at the front of the
container, which is why texpack reads that table.  These archives do not: the record itself
opens with them.  The first record of 0001 begins 00 02 00 01 20 00 20 00 05 00 03 00 78, which
reads as 512 wide, 256 high, tiles of 32, format 5 -- the same GU_PSM_T8 the UI textures use --
and pixel data starting 120 bytes in.

That is enough to draw it.  Whether the result is a scene, a menu or noise decides whether
these archives have anything to do with the title screen, and looking is quicker than
finishing the format.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

import numpy as np
from PIL import Image

import lzss
import texpack

ROOT = Path(r"D:\psp\원격수사")
ISO = ROOT / "iso_extract" / "PSP_GAME" / "USRDIR"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default="0001")
    parser.add_argument("--stream", type=lambda v: int(v, 0), default=0x840)
    parser.add_argument("--record", type=int, default=2)
    parser.add_argument("--palette", type=int, default=1)
    parser.add_argument("--tiles", action="store_true",
                        help="lay the data out as the tiles the header describes")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "scene_try.png")
    args = parser.parse_args()

    blob = (ISO / args.file).read_bytes()
    plain, _ = lzss.decompress(blob, args.stream, limit=64 << 20)
    records = texpack.load_records(plain)
    data = records[args.record]
    width, height, tw, th, psm, flag, start = struct.unpack_from("<7H", data, 0)[:7]
    start = struct.unpack_from("<I", data, 12)[0]
    print(f"{args.file}@{args.stream:#x} record {args.record}: {len(data)} bytes")
    print(f"   header says {width} x {height}, tile {tw}x{th}, psm {psm}, "
          f"flag {flag}, pixels start {start:#x}")

    pixels = data[start:]
    byte_width = width // 2 if psm == 4 else width
    have = len(pixels)
    rows = min(height, have // max(1, byte_width))
    print(f"   {have} bytes of pixel data covers {rows} of {height} rows")
    if rows < 1:
        raise SystemExit("not enough data to draw anything")

    if args.tiles:
        # The header carries a tile size, which stream0's textures do not.  Laid out as one
        # long scanline the picture came out as horizontal smears, which is what a tiled image
        # looks like when it is read as if it were not: 32x32 blocks stored one after another
        # in reading order, each block internally a plain raster.
        cols = width // tw
        whole = have // (tw * th)
        buf = np.frombuffer(pixels[:whole * tw * th], dtype=np.uint8)
        tiles = buf.reshape(whole, th, tw)
        rows = ((whole + cols - 1) // cols) * th
        plane = np.zeros((rows, byte_width), dtype=np.uint8)
        for n, tile in enumerate(tiles):
            r, c = divmod(n, cols)
            plane[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = tile
        print(f"   {whole} tiles of {tw}x{th} placed {cols} per row")
    else:
        buf = np.frombuffer(pixels[:byte_width * rows], dtype=np.uint8)
        plane = texpack.unswizzle(buf, byte_width, rows)
    if psm == 4:
        idx = np.empty((rows, width), dtype=np.uint8)
        idx[:, 0::2] = plane & 0x0F
        idx[:, 1::2] = plane >> 4
    else:
        idx = plane

    pal = np.frombuffer(records[args.palette], dtype=np.uint8)
    pal = pal[:1024].reshape(-1, 4)
    if len(pal) < 256:
        pal = np.vstack([pal, np.zeros((256 - len(pal), 4), np.uint8)])
    rgba = pal[idx]
    Image.fromarray(rgba, "RGBA").save(args.out)
    print(f"-> {args.out} ({width}x{rows})")


if __name__ == "__main__":
    main()

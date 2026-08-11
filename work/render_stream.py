"""Render a stream's palette+image record pair with an explicit width / format."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

import texpack


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stream", type=Path)
    parser.add_argument("--pal", type=int, default=1)
    parser.add_argument("--img", type=int, default=2)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--bpp", type=int, default=8, choices=(4, 8))
    parser.add_argument("--skip", type=lambda v: int(v, 0), default=0, help="bytes to skip in the image record")
    parser.add_argument("--linear", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    records = texpack.load_records(args.stream.read_bytes())
    palette = records[args.pal]
    image = records[args.img][args.skip :]
    byte_width = args.width // 2 if args.bpp == 4 else args.width
    height = len(image) // byte_width
    print(f"records={[hex(len(r)) for r in records]}  {args.width}x{height} {args.bpp}bpp")

    buf = np.frombuffer(image[: byte_width * height], dtype=np.uint8)
    plane = buf.reshape(height, byte_width) if args.linear else texpack.unswizzle(buf, byte_width, height)
    if args.bpp == 4:
        indices = np.empty((height, args.width), dtype=np.uint8)
        indices[:, 0::2] = plane & 0x0F
        indices[:, 1::2] = plane >> 4
    else:
        indices = plane

    colours = np.frombuffer(palette, dtype=np.uint8).reshape(-1, 4)
    Image.fromarray(colours[indices], "RGBA").save(args.out)
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

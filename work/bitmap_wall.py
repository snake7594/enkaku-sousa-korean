"""Render a raw byte range as a bitmap so glyph data becomes visible by eye.

Supports 1/2/4/8 bits per pixel and an optional glyph-cell layout, which lays
consecutive fixed-size cells out in a grid (how a font would be stored).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def unpack_bits(data: bytes, bpp: int) -> np.ndarray:
    buf = np.frombuffer(data, dtype=np.uint8)
    if bpp == 8:
        return buf
    if bpp == 4:
        out = np.empty(buf.size * 2, dtype=np.uint8)
        out[0::2] = buf >> 4
        out[1::2] = buf & 0x0F
        return out * 17
    if bpp == 2:
        out = np.empty(buf.size * 4, dtype=np.uint8)
        for i in range(4):
            out[i::4] = (buf >> (6 - 2 * i)) & 0x03
        return out * 85
    if bpp == 1:
        bits = np.unpackbits(buf)
        return bits * 255
    raise ValueError(bpp)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--offset", type=lambda v: int(v, 0), default=0)
    parser.add_argument("--length", type=lambda v: int(v, 0), default=0x20000)
    parser.add_argument("--bpp", type=int, default=1, choices=(1, 2, 4, 8))
    parser.add_argument("--cell", type=int, nargs=2, default=None, help="glyph cell w h")
    parser.add_argument("--columns", type=int, default=32)
    parser.add_argument("--width", type=int, default=512, help="used when --cell is absent")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    data = args.path.read_bytes()[args.offset : args.offset + args.length]
    pixels = unpack_bits(data, args.bpp)

    if args.cell:
        cw, ch = args.cell
        per_cell = cw * ch
        count = len(pixels) // per_cell
        cells = pixels[: count * per_cell].reshape(count, ch, cw)
        rows = (count + args.columns - 1) // args.columns
        sheet = np.zeros((rows * ch, args.columns * cw), dtype=np.uint8)
        for i in range(count):
            r, c = divmod(i, args.columns)
            sheet[r * ch : (r + 1) * ch, c * cw : (c + 1) * cw] = cells[i]
        image = Image.fromarray(sheet, "L")
        print(f"{count} cells of {cw}x{ch} @ {args.bpp}bpp -> {args.out}")
    else:
        rows = len(pixels) // args.width
        image = Image.fromarray(pixels[: rows * args.width].reshape(rows, args.width), "L")
        print(f"{args.width}x{rows} @ {args.bpp}bpp -> {args.out}")

    image.save(args.out)


if __name__ == "__main__":
    main()

"""Render an arbitrary file region as 4bpp glyphs, to see whether it really is a font.

The scan that ranks regions by "glyphiness" cannot tell a bitmap font from MIPS code -- both
have structure at 128-byte intervals.  Drawing the candidate settles it in one look.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(r"D:\psp\원격수사")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--offset", type=lambda v: int(v, 0), required=True)
    parser.add_argument("--glyphs", type=int, default=64)
    parser.add_argument("--cols", type=int, default=16)
    parser.add_argument("--scale", type=int, default=4)
    parser.add_argument("--tiled", action="store_true",
                        help="treat the data as 32x16 tiles holding two glyphs, as stream1 does")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    blob = args.file.read_bytes()
    need = args.glyphs * 128
    chunk = blob[args.offset:args.offset + need]
    if len(chunk) < need:
        raise SystemExit("not enough data at that offset")

    nib = np.frombuffer(chunk, dtype=np.uint8)
    nib = np.stack([nib & 0x0F, nib >> 4], axis=1).reshape(-1)
    if args.tiled:
        planes = nib.reshape(args.glyphs // 2, 16, 32)
        cells = np.concatenate([planes[:, :, :16], planes[:, :, 16:]], axis=0)
    else:
        cells = nib.reshape(args.glyphs, 16, 16)

    rows = (len(cells) + args.cols - 1) // args.cols
    sheet = np.zeros((rows * 17, args.cols * 17), dtype=np.uint8)
    for n, cell in enumerate(cells):
        r, c = divmod(n, args.cols)
        sheet[r * 17:r * 17 + 16, c * 17:c * 17 + 16] = cell * 17
    image = Image.fromarray(sheet, "L").resize(
        (sheet.shape[1] * args.scale, sheet.shape[0] * args.scale), Image.NEAREST)
    image.save(args.out)
    print(f"{args.file.name} {args.offset:#x}, {len(cells)} cells "
          f"({'tiled' if args.tiled else 'flat'}) -> {args.out} {image.size}")


if __name__ == "__main__":
    main()

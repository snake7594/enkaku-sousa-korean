"""Build a contact sheet from PPSSPP's dumped glyph tiles, on a dark background so
white antialiased glyphs are visible."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--size", type=int, nargs=2, default=(32, 32))
    parser.add_argument("--columns", type=int, default=24)
    parser.add_argument("--count", type=int, default=288)
    parser.add_argument("--skip", type=int, default=0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    want = tuple(args.size)
    tiles = []
    for path in sorted(args.folder.rglob("*.png")):
        try:
            im = Image.open(path)
            if im.size != want:
                continue
            tiles.append(im.convert("RGBA"))
        except Exception:  # noqa: BLE001
            continue
        if len(tiles) >= args.skip + args.count:
            break

    tiles = tiles[args.skip :]
    if not tiles:
        print("no tiles matched")
        return

    rows = (len(tiles) + args.columns - 1) // args.columns
    sheet = Image.new("RGBA", (want[0] * args.columns, want[1] * rows), (16, 16, 24, 255))
    for i, tile in enumerate(tiles):
        sheet.alpha_composite(tile, ((i % args.columns) * want[0], (i // args.columns) * want[1]))
    sheet.convert("RGB").save(args.out)

    sample = np.asarray(tiles[0])
    print(f"{len(tiles)} tiles {want[0]}x{want[1]} -> {args.out}")
    print(f"sample alpha range {sample[..., 3].min()}-{sample[..., 3].max()}, "
          f"rgb range {sample[..., :3].min()}-{sample[..., :3].max()}")


if __name__ == "__main__":
    main()

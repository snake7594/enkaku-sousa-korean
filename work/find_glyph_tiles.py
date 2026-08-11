"""Isolate PPSSPP-dumped tiles that are pure-white alpha masks — i.e. font glyphs."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def is_alpha_mask(arr: np.ndarray) -> bool:
    rgb = arr[..., :3]
    alpha = arr[..., 3]
    if alpha.max() == 0:
        return False
    ink = alpha > 8
    if not ink.any():
        return False
    # glyph masks carry no colour of their own: RGB is a single flat value
    return len(np.unique(rgb[ink])) <= 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--columns", type=int, default=32)
    parser.add_argument("--limit", type=int, default=512)
    parser.add_argument("--size", type=int, nargs=2, default=(32, 32))
    args = parser.parse_args()

    want = tuple(args.size)
    glyphs = []
    scanned = 0
    for path in sorted(args.folder.rglob("*.png")):
        try:
            im = Image.open(path)
            if im.size != want:
                continue
            arr = np.asarray(im.convert("RGBA"))
        except Exception:  # noqa: BLE001
            continue
        scanned += 1
        if is_alpha_mask(arr):
            glyphs.append((path.name, arr))

    print(f"scanned {scanned} tiles of {want[0]}x{want[1]}, {len(glyphs)} are flat-colour alpha masks")
    if not glyphs:
        return

    tiles = glyphs[: args.limit]
    rows = (len(tiles) + args.columns - 1) // args.columns
    sheet = Image.new("RGBA", (want[0] * args.columns, want[1] * rows), (16, 16, 24, 255))
    for i, (_, arr) in enumerate(tiles):
        rgba = arr.copy()
        rgba[..., :3] = 255
        sheet.alpha_composite(
            Image.fromarray(rgba, "RGBA"), ((i % args.columns) * want[0], (i // args.columns) * want[1])
        )
    sheet.convert("RGB").save(args.out)
    print(f"-> {args.out} ({len(tiles)} glyphs)")


if __name__ == "__main__":
    main()

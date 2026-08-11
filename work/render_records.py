"""Render the paletted records of a decompressed stream to PNG contact sheets.

Records alternate palette / image.  A 0x40 palette means 16 colours (4bpp),
0x400 means 256 colours (8bpp).  PSP textures are usually swizzled in 16x8 byte
blocks, so both the swizzled and linear reading are produced.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

from records import load_records


def unswizzle(buf: np.ndarray, byte_width: int, height: int) -> np.ndarray:
    """Undo the PSP GE 16x8-byte block swizzle."""
    if byte_width % 16 or height % 8:
        return buf.reshape(height, byte_width)
    blocks_per_row = byte_width // 16
    block_rows = height // 8
    blocks = buf.reshape(block_rows, blocks_per_row, 8, 16)
    return blocks.transpose(0, 2, 1, 3).reshape(height, byte_width)


def decode(image: bytes, palette: bytes, byte_width: int, swizzled: bool) -> Image.Image | None:
    bpp = 4 if len(palette) == 0x40 else 8
    if len(image) % byte_width:
        return None
    height = len(image) // byte_width
    if height == 0:
        return None
    buf = np.frombuffer(image, dtype=np.uint8)
    plane = unswizzle(buf, byte_width, height) if swizzled else buf.reshape(height, byte_width)

    if bpp == 4:
        low = plane & 0x0F
        high = plane >> 4
        indices = np.empty((height, byte_width * 2), dtype=np.uint8)
        indices[:, 0::2] = low
        indices[:, 1::2] = high
    else:
        indices = plane

    colours = np.frombuffer(palette, dtype=np.uint8).reshape(-1, 4)
    rgba = colours[indices]
    return Image.fromarray(rgba, "RGBA")


def contact_sheet(images: list[tuple[str, Image.Image]], columns: int, path: Path) -> None:
    if not images:
        return
    cell_w = max(im.width for _, im in images)
    cell_h = max(im.height for _, im in images)
    rows = (len(images) + columns - 1) // columns
    sheet = Image.new("RGBA", (cell_w * columns, cell_h * rows), (255, 0, 255, 255))
    for i, (_, im) in enumerate(images):
        sheet.paste(im, ((i % columns) * cell_w, (i // columns) * cell_h))
    sheet.save(path)
    print(f"contact sheet -> {path} ({len(images)} tiles, cell {cell_w}x{cell_h})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stream", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--indices", type=int, nargs="*", default=None)
    parser.add_argument("--width", type=int, default=None, help="pixel width override")
    parser.add_argument("--linear", action="store_true")
    args = parser.parse_args()

    records = load_records(args.stream)
    args.out.mkdir(parents=True, exist_ok=True)

    pairs = []
    for i in range(len(records) - 1):
        if len(records[i]) in (0x40, 0x400) and len(records[i + 1]) >= 0x400:
            pairs.append((i, i + 1))

    wanted = set(args.indices) if args.indices else None
    made = []
    for pal_i, img_i in pairs:
        if wanted and img_i not in wanted and pal_i not in wanted:
            continue
        palette, image = records[pal_i], records[img_i]
        bpp = 4 if len(palette) == 0x40 else 8
        widths = [args.width] if args.width else [128, 256, 512]
        for pixel_width in widths:
            byte_width = pixel_width // 2 if bpp == 4 else pixel_width
            im = decode(image, palette, byte_width, swizzled=not args.linear)
            if im is None:
                continue
            name = f"r{img_i:04d}_pal{pal_i:04d}_{bpp}bpp_w{pixel_width}.png"
            im.save(args.out / name)
            made.append((name, im))
    print(f"rendered {len(made)} images -> {args.out}")


if __name__ == "__main__":
    main()

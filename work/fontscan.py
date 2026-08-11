"""Locate 16x16 8bpp glyph tables inside decompressed streams.

A glyph cell is 256 bytes (16 rows x 16 columns, one byte of coverage per pixel).
Real glyphs have ink in the middle and a mostly-empty margin, so cells are scored
on that shape rather than on entropy alone.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

CELL = 16
CELL_BYTES = CELL * CELL


def cells_of(data: bytes, offset: int) -> np.ndarray:
    usable = (len(data) - offset) // CELL_BYTES * CELL_BYTES
    buf = np.frombuffer(data[offset : offset + usable], dtype=np.uint8)
    return buf.reshape(-1, CELL, CELL)


def glyph_score(cells: np.ndarray) -> np.ndarray:
    """Per-cell boolean: does this look like a rendered glyph?"""
    ink = cells > 24
    density = ink.mean(axis=(1, 2))
    # glyphs leave the outermost row/column almost empty
    border = np.concatenate(
        [ink[:, 0, :], ink[:, -1, :], ink[:, :, 0], ink[:, :, -1]], axis=1
    ).mean(axis=1)
    blank = density < 0.01
    good = (density > 0.03) & (density < 0.80) & (border < 0.35)
    return good | blank


def find_runs(flags: np.ndarray, min_len: int = 32, tolerance: int = 8) -> list[tuple[int, int]]:
    runs = []
    start = None
    misses = 0
    for i, ok in enumerate(flags):
        if ok:
            if start is None:
                start = i
            misses = 0
        elif start is not None:
            misses += 1
            if misses > tolerance:
                if i - misses - start >= min_len:
                    runs.append((start, i - misses))
                start = None
                misses = 0
    if start is not None and len(flags) - start >= min_len:
        runs.append((start, len(flags)))
    return runs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", type=Path, nargs="+")
    parser.add_argument("--align", type=lambda v: int(v, 0), default=0x90,
                        help="byte offset the glyph table starts at")
    parser.add_argument("--min-glyphs", type=int, default=64)
    parser.add_argument("--export", type=Path, default=None)
    args = parser.parse_args()

    for path in args.paths:
        targets = sorted(path.rglob("*.bin")) if path.is_dir() else [path]
        for target in targets:
            data = target.read_bytes()
            if len(data) < args.align + CELL_BYTES * args.min_glyphs:
                continue
            cells = cells_of(data, args.align)
            flags = glyph_score(cells)
            runs = find_runs(flags, min_len=args.min_glyphs)
            runs = [(a, b) for a, b in runs if (cells[a:b] > 24).mean() > 0.02]
            if not runs:
                continue
            for a, b in runs:
                start = args.align + a * CELL_BYTES
                end = args.align + b * CELL_BYTES
                print(f"{target.name}: glyphs {b - a:5d}  bytes 0x{start:x}-0x{end:x}")
                if args.export:
                    args.export.mkdir(parents=True, exist_ok=True)
                    block = cells[a:b]
                    columns = 64
                    rows = (len(block) + columns - 1) // columns
                    sheet = np.zeros((rows * CELL, columns * CELL), dtype=np.uint8)
                    for i, cell in enumerate(block):
                        r, c = divmod(i, columns)
                        sheet[r * CELL : (r + 1) * CELL, c * CELL : (c + 1) * CELL] = cell
                    name = f"{target.stem}_0x{start:x}_{b - a}glyphs.png"
                    Image.fromarray(sheet, "L").save(args.export / name)


if __name__ == "__main__":
    main()

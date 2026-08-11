"""Detect 16x16 8bpp glyph tables using the side-bearing signature.

Every rendered glyph leaves its leftmost and rightmost pixel column empty (side
bearing).  Across a real font table that holds for nearly every cell, while random
or compressed bytes almost never satisfy it.  That single property separates the
font from everything else far more reliably than entropy or smoothness.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

CELL_BYTES = 256


def cells_at(data: bytes, offset: int) -> np.ndarray:
    usable = (len(data) - offset) // CELL_BYTES * CELL_BYTES
    if usable <= 0:
        return np.empty((0, 16, 16), dtype=np.uint8)
    return np.frombuffer(data[offset : offset + usable], dtype=np.uint8).reshape(-1, 16, 16)


def side_bearing(cells: np.ndarray) -> np.ndarray:
    """Per-cell: are the outer columns empty (and the cell non-blank)?"""
    quiet = (cells[:, :, 0] < 8).all(axis=1) & (cells[:, :, 15] < 8).all(axis=1)
    return quiet


def best_alignment(data: bytes, window: int = 4096) -> tuple[int, float]:
    best = (0, 0.0)
    for offset in range(0, min(CELL_BYTES, len(data))):
        cells = cells_at(data, offset)[:window]
        if len(cells) < 64:
            continue
        score = float(side_bearing(cells).mean())
        if score > best[1]:
            best = (offset, score)
    return best


def runs_of(flags: np.ndarray, min_len: int, tolerance: int) -> list[tuple[int, int]]:
    runs, start, misses = [], None, 0
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
                start, misses = None, 0
    if start is not None and len(flags) - start >= min_len:
        runs.append((start, len(flags)))
    return runs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", type=Path, nargs="+")
    parser.add_argument("--min-glyphs", type=int, default=48)
    parser.add_argument("--tolerance", type=int, default=6)
    parser.add_argument("--export", type=Path, default=None)
    parser.add_argument("--columns", type=int, default=64)
    args = parser.parse_args()

    for path in args.paths:
        targets = sorted(path.rglob("*.bin")) if path.is_dir() else [path]
        for target in targets:
            data = target.read_bytes()
            if len(data) < CELL_BYTES * args.min_glyphs:
                continue
            offset, score = best_alignment(data)
            if score < 0.5:
                continue
            cells = cells_at(data, offset)
            flags = side_bearing(cells)
            for a, b in runs_of(flags, args.min_glyphs, args.tolerance):
                block = cells[a:b]
                if (block > 24).mean() < 0.03:
                    continue
                start = offset + a * CELL_BYTES
                print(f"{target.name}: {b - a:5d} glyphs at 0x{start:x}-0x{offset + b * CELL_BYTES:x} "
                      f"(align 0x{offset:x}, bearing {score:.2f})")
                if args.export:
                    args.export.mkdir(parents=True, exist_ok=True)
                    rows = (len(block) + args.columns - 1) // args.columns
                    sheet = np.zeros((rows * 16, args.columns * 16), dtype=np.uint8)
                    for i, cell in enumerate(block):
                        r, c = divmod(i, args.columns)
                        sheet[r * 16 : r * 16 + 16, c * 16 : c * 16 + 16] = cell
                    out = args.export / f"{target.stem}_0x{start:x}_{b - a}.png"
                    Image.fromarray(sheet, "L").save(out)


if __name__ == "__main__":
    main()

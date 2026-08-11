"""Scan decompressed streams (and raw files) for 원격수사 glyph tables."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

import font


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


def scan_file(path: Path, min_tiles: int, tolerance: int) -> list[font.FontBlock]:
    data = path.read_bytes()
    if len(data) < font.TILE_BYTES * min_tiles:
        return []
    best: list[font.FontBlock] = []
    # the table can start at any 16-byte row boundary within a tile
    for align in range(0, font.TILE_BYTES, 16):
        pixels = font.tile_pixels(data, align)
        if len(pixels) < min_tiles:
            continue
        flags = font.is_glyph_tile(pixels)
        ink = (pixels > 2).mean(axis=(1, 2))
        flags = flags & (ink > 0.05) & (ink < 0.75)
        for a, b in runs_of(flags, min_tiles, tolerance):
            best.append(font.FontBlock(path, align + a * font.TILE_BYTES, b - a))
    # keep the longest non-overlapping blocks
    best.sort(key=lambda b: -b.tiles)
    chosen: list[font.FontBlock] = []
    for block in best:
        if any(block.offset < c.end and c.offset < block.end for c in chosen):
            continue
        chosen.append(block)
    return sorted(chosen, key=lambda b: b.offset)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", type=Path, nargs="+")
    parser.add_argument("--min-tiles", type=int, default=48)
    parser.add_argument("--tolerance", type=int, default=4)
    parser.add_argument("--export", type=Path, default=None)
    args = parser.parse_args()

    total = 0
    for root in args.paths:
        targets = sorted(root.rglob("*")) if root.is_dir() else [root]
        for target in targets:
            if not target.is_file():
                continue
            for block in scan_file(target, args.min_tiles, args.tolerance):
                total += block.glyphs
                print(f"{target.name:32s} 0x{block.offset:08x}-0x{block.end:08x}  "
                      f"{block.tiles:5d} tiles = {block.glyphs:5d} glyphs")
                if args.export:
                    args.export.mkdir(parents=True, exist_ok=True)
                    data = target.read_bytes()
                    glyphs = font.tiles_to_glyphs(data, block.offset, block.tiles)
                    out = args.export / f"{target.stem}_0x{block.offset:x}_{block.glyphs}glyphs.png"
                    font.sheet(glyphs, columns=64).save(out)
    print(f"\ntotal {total} glyphs")


if __name__ == "__main__":
    main()

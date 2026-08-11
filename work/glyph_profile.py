"""Print a per-block profile of glyph-likeness so the font table's extent is visible."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

CELL_BYTES = 256


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--offset", type=lambda v: int(v, 0), default=0x90)
    parser.add_argument("--length", type=lambda v: int(v, 0), default=0)
    parser.add_argument("--group", type=int, default=64, help="cells per printed line")
    args = parser.parse_args()

    data = args.path.read_bytes()
    end = len(data) if not args.length else min(len(data), args.offset + args.length)
    usable = (end - args.offset) // CELL_BYTES * CELL_BYTES
    cells = np.frombuffer(data[args.offset : args.offset + usable], dtype=np.uint8).reshape(-1, 16, 16)

    ink = cells > 24
    density = ink.mean(axis=(1, 2))
    # Rendered glyphs are locally smooth: neighbouring pixels rarely jump by much.
    # Random/compressed bytes average ~85 per step, so this separates them cleanly
    # even for dense CJK glyphs that fill the whole cell.
    step = np.abs(cells[:, :, 1:].astype(np.int16) - cells[:, :, :-1].astype(np.int16)).mean(axis=(1, 2))

    print(f"{len(cells)} cells from 0x{args.offset:x}")
    print("offset      cells  mean_density  mean_step  verdict")
    for start in range(0, len(cells), args.group):
        block = slice(start, start + args.group)
        d = density[block]
        s = step[block]
        verdict = "GLYPHS" if s.mean() < 40 else "noise/other"
        print(f"0x{args.offset + start * CELL_BYTES:08x}  {start:5d}  "
              f"{d.mean():.3f}         {s.mean():6.1f}     {verdict}")


if __name__ == "__main__":
    main()

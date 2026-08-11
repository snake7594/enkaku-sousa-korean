"""Find candidate text runs in the script bytecode and render them with the real font.

The glyph table has 1368 entries, so if strings are stored as glyph indices they
must be u16 values below 1368 — meaning the high byte of every code sits in
0x00..0x05.  A run of those with varied low bytes is a string candidate, and the
only honest way to confirm it is to draw it with the extracted glyphs and look.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

import font as fontlib

STREAM = Path(r"D:\psp\원격수사\font_extract\script_stream.bin")
FONT_OFFSET = 0x80
FONT_TILES = 684
GLYPH_COUNT = FONT_TILES * 2
CODE_START = FONT_OFFSET + FONT_TILES * fontlib.TILE_BYTES  # 0x2AC80


def load_glyphs() -> np.ndarray:
    return fontlib.tiles_to_glyphs(STREAM.read_bytes(), FONT_OFFSET, FONT_TILES)


def find_runs(data: bytes, start: int, end: int, min_len: int) -> list[tuple[int, int, list[int]]]:
    """Runs of u16 LE values in [1, GLYPH_COUNT) at even offsets from `start`."""
    runs = []
    for parity in (0, 1):
        pos = start + parity
        codes: list[int] = []
        run_start = pos
        while pos + 1 < end:
            value = data[pos] | (data[pos + 1] << 8)
            if 0 < value < GLYPH_COUNT:
                if not codes:
                    run_start = pos
                codes.append(value)
            else:
                if len(codes) >= min_len:
                    runs.append((run_start, pos, codes))
                codes = []
            pos += 2
        if len(codes) >= min_len:
            runs.append((run_start, pos, codes))
    runs.sort()
    return runs


def render(codes: list[int], glyphs: np.ndarray, per_line: int = 40) -> Image.Image:
    lines = [codes[i : i + per_line] for i in range(0, len(codes), per_line)]
    width = max(len(line) for line in lines) * fontlib.GLYPH_W
    canvas = np.zeros((len(lines) * fontlib.GLYPH_H, width), dtype=np.uint8)
    for r, line in enumerate(lines):
        for c, code in enumerate(line):
            if code < len(glyphs):
                canvas[r * 16 : r * 16 + 16, c * 16 : c * 16 + 16] = glyphs[code] * 17
    return Image.fromarray(canvas, "L")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=lambda v: int(v, 0), default=CODE_START)
    parser.add_argument("--end", type=lambda v: int(v, 0), default=0)
    parser.add_argument("--min-len", type=int, default=8)
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--render", type=Path, default=None)
    parser.add_argument("--render-count", type=int, default=6)
    args = parser.parse_args()

    data = STREAM.read_bytes()
    end = args.end or len(data)
    runs = find_runs(data, args.start, end, args.min_len)
    total = sum(len(codes) for _, _, codes in runs)
    print(f"{len(runs)} candidate runs, {total} codes total, in 0x{args.start:x}-0x{end:x}")

    longest = sorted(runs, key=lambda r: -len(r[2]))[: args.top]
    for run_start, run_end, codes in longest:
        preview = " ".join(f"{c:03x}" for c in codes[:16])
        print(f"   0x{run_start:08x} len={len(codes):4d}  {preview}")

    if args.render:
        args.render.mkdir(parents=True, exist_ok=True)
        glyphs = load_glyphs()
        for run_start, _, codes in longest[: args.render_count]:
            image = render(codes, glyphs)
            image.save(args.render / f"run_0x{run_start:x}_{len(codes)}.png")
        print(f"rendered {min(args.render_count, len(longest))} runs -> {args.render}")


if __name__ == "__main__":
    main()

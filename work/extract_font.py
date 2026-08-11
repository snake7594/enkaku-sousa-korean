"""원격수사 폰트 추출/재삽입.

폰트 위치
---------
ISO -> /PSP_GAME/USRDIR/0000 -> 0x27E000 의 LZ11 스트림 -> 압축 해제본의 0x80
16x16 4bpp 글리프가 32x16 타일(=글리프 2개, 256바이트) 단위로 연속 배치된다.

    python extract_font.py --sheet font.png --raw font.bin
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

import font as fontlib
import lzss

ISO = Path(r"D:\psp\원격수사\Enkaku Sousa Shinjitsu eno 23nichikan.iso")
ARCHIVE = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR\0000")

STREAM_OFFSET = 0x27E000   # LZ11 stream inside 0000
FONT_OFFSET = 0x80         # start of the glyph table inside the decompressed stream


def load_stream() -> bytes:
    data = ARCHIVE.read_bytes()
    plain, consumed = lzss.decompress(data, STREAM_OFFSET)
    print(f"0000 @0x{STREAM_OFFSET:x}: packed 0x{consumed:x} -> plain 0x{len(plain):x}")
    return plain


def font_extent(plain: bytes) -> int:
    """Number of 32x16 tiles before the script bytecode starts."""
    pixels = fontlib.tile_pixels(plain, FONT_OFFSET)
    ok = fontlib.is_glyph_tile(pixels)
    ink = (pixels > 2).mean(axis=(1, 2))
    ok = ok & (ink > 0.03)
    misses = 0
    for i, flag in enumerate(ok):
        if flag:
            misses = 0
            continue
        misses += 1
        if misses > 8:
            return i - misses + 1
    return len(ok)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet", type=Path, default=None)
    parser.add_argument("--raw", type=Path, default=None)
    parser.add_argument("--stream", type=Path, default=None, help="also save the decompressed stream")
    parser.add_argument("--columns", type=int, default=64)
    parser.add_argument("--tiles", type=int, default=None, help="override the detected tile count")
    args = parser.parse_args()

    plain = load_stream()
    if args.stream:
        args.stream.write_bytes(plain)
        print(f"stream -> {args.stream}")

    tiles = args.tiles if args.tiles is not None else font_extent(plain)
    end = FONT_OFFSET + tiles * fontlib.TILE_BYTES
    print(f"font: 0x{FONT_OFFSET:x}-0x{end:x}  {tiles} tiles = {tiles * 2} glyphs "
          f"({tiles * fontlib.TILE_BYTES} bytes)")

    glyphs = fontlib.tiles_to_glyphs(plain, FONT_OFFSET, tiles)
    used = int(np.sum((glyphs > 2).any(axis=(1, 2))))
    print(f"non-blank glyphs: {used}")

    if args.raw:
        args.raw.write_bytes(plain[FONT_OFFSET:end])
        print(f"raw glyph data -> {args.raw}")
    if args.sheet:
        fontlib.sheet(glyphs, columns=args.columns).save(args.sheet)
        print(f"sheet -> {args.sheet}")


if __name__ == "__main__":
    main()

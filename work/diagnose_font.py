"""Why did the glyph replacement not show up in game?

The line changed on screen but the glyphs did not, and the characters displayed look
like the originals of those slots.  Either the game reads its glyphs from a second copy
of the font, or the patched copy is not the one it loads.  This renders the original
slots for comparison and searches the whole ISO for duplicates of the glyph data.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

import font as fontlib
import lzss
from iso9660 import BLOCK, find_record, list_records

ORIG_ISO = Path(r"D:\psp\원격수사\Enkaku Sousa Shinjitsu eno 23nichikan.iso")
TEST_ISO = Path(r"D:\psp\원격수사\build\Enkaku_hangul_test.iso")
STREAM1 = 0x27E000
FONT_OFFSET = 0x80
FONT_TILES = 684


def slot_sheet(glyphs: np.ndarray, first: int, count: int, path: Path, scale: int = 6) -> None:
    sheet = np.zeros((16, 16 * count), dtype=np.uint8)
    for k in range(count):
        sheet[:, k * 16 : (k + 1) * 16] = glyphs[first + k] * 17
    Image.fromarray(sheet, "L").resize((16 * count * scale, 16 * scale), Image.NEAREST).save(path)


def font_of(iso_bytes: bytes) -> np.ndarray:
    record = find_record(iso_bytes, "/PSP_GAME/USRDIR/0000")
    archive = iso_bytes[record.extent * BLOCK : record.extent * BLOCK + record.size]
    plain, _ = lzss.decompress(archive, STREAM1)
    return fontlib.tiles_to_glyphs(plain, FONT_OFFSET, FONT_TILES), plain


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", type=int, default=1349)
    parser.add_argument("--count", type=int, default=10)
    args = parser.parse_args()

    original = ORIG_ISO.read_bytes()
    patched = TEST_ISO.read_bytes()

    orig_glyphs, orig_plain = font_of(original)
    new_glyphs, _ = font_of(patched)
    slot_sheet(orig_glyphs, args.first, args.count, Path(r"D:\psp\원격수사\dump\slots_original.png"))
    slot_sheet(new_glyphs, args.first, args.count, Path(r"D:\psp\원격수사\dump\slots_patched.png"))
    print("rendered original vs patched slots")

    # does the glyph data appear anywhere else in the ISO?
    tile_index = args.first // 2
    probe = orig_plain[FONT_OFFSET + tile_index * 256 : FONT_OFFSET + (tile_index + 4) * 256]
    print(f"\nsearching the ISO for the raw glyph bytes ({len(probe)} bytes) ...")
    hits, start = [], 0
    while len(hits) < 8:
        idx = original.find(probe, start)
        if idx < 0:
            break
        hits.append(idx)
        start = idx + 1
    print(f"   raw (uncompressed) copies in the ISO: {[hex(h) for h in hits]}")

    # which ISO files could hold a compressed copy?
    print("\n   files in the ISO:")
    for record in list_records(original):
        if not (record.flags & 2):
            print(f"      {record.name:<44} lba={record.extent:<8} size={record.size}")


if __name__ == "__main__":
    main()

"""Put Korean into the save menu, which lives in the executable rather than in a texture.

The renderer picks its font from where the string sits (0x884be84), and for strings inside the
executable that font is at 0x88EA760 -- 436 tiles, 872 glyphs, ending exactly where the string
data begins.  Reading every string in the file leaves five glyph slots nobody addresses, which
is enough for 저장 and 삭제.

Both strings can be rewritten where they are.  セーブ is BE B0 83 75 00 and 削除 is 89 48 89 49
00, five bytes each, and two kanji-slot characters plus the terminator is also five.  Nothing
moves, so no pointer needs touching.

The glyphs go into the unused slots rather than over 削 and 除, which appear in other strings.
A byte pair matching a free slot does turn up here and there in the file, but those are code and
data rather than text -- the scan that found them read strings, not bytes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"D:\psp\원격수사")
BOOT = ROOT / "iso_extract" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN"
GOTHIC = Path(r"C:\Windows\Fonts\malgunbd.ttf")
VADDR_TO_FILE = 0x8803FAC
KANJI_FONT = 0x88EA760

# glyph slot -> the syllable to draw there.  Slots come from work/scan_boot_glyphs.py.
GLYPHS = {864: "저", 866: "장", 869: "삭", 870: "제"}

# file offset -> (what is there now, what to write).  Lengths must match.
STRINGS = {
    0x103708: ("セーブ", "저장"),      # vaddr 0x89076b4, pointer table entry 0
    0x10370D: ("削除", "삭제"),        # vaddr 0x89076b9, entry 1
}


def code_for(index: int) -> bytes:
    return bytes([0x88 + index // 253, index % 253])


def render(char: str, font_path: Path, size: int) -> np.ndarray:
    image = Image.new("L", (16, 16), 0)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), size)
    box = draw.textbbox((0, 0), char, font=font)
    draw.text(((16 - (box[2] - box[0])) / 2 - box[0],
               (16 - (box[3] - box[1])) / 2 - box[1]), char, font=font, fill=255)
    return (np.asarray(image).astype(np.uint16) * 15 // 255).astype(np.uint8)


def write_glyph(data: bytearray, base: int, index: int, cell: np.ndarray) -> None:
    tile, half = divmod(index, 2)
    at = base + tile * 256
    raw = np.frombuffer(bytes(data[at:at + 256]), dtype=np.uint8)
    nib = np.stack([raw & 0x0F, raw >> 4], axis=1).reshape(16, 32).copy()
    nib[:, half * 16:half * 16 + 16] = cell
    flat = nib.reshape(-1)
    packed = (flat[0::2] | (flat[1::2] << 4)).astype(np.uint8)
    data[at:at + 256] = packed.tobytes()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=BOOT)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "BOOT_ko.BIN")
    parser.add_argument("--font", type=Path, default=GOTHIC)
    parser.add_argument("--size", type=int, default=15)
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "boot_patch.json")
    args = parser.parse_args()

    data = bytearray(args.file.read_bytes())
    base = KANJI_FONT - VADDR_TO_FILE
    slot_of = {char: index for index, char in GLYPHS.items()}

    for index, char in GLYPHS.items():
        write_glyph(data, base, index, render(char, args.font, args.size))
        print(f"   glyph {index:4d} <- {char}   ({code_for(index).hex(' ')})")

    changes = []
    for offset, (before, after) in STRINGS.items():
        old = bytes(data[offset:offset + 5])
        new = b"".join(code_for(slot_of[c]) for c in after) + b"\0"
        if len(new) != 5:
            raise SystemExit(f"{after} encodes to {len(new)} bytes, not 5")
        data[offset:offset + 5] = new
        changes.append({"offset": offset, "ja": before, "ko": after,
                        "was": old.hex(" "), "now": new.hex(" ")})
        print(f"   {offset:#x}  {before} -> {after}   {old.hex(' ')} -> {new.hex(' ')}")

    args.out.write_bytes(bytes(data))
    args.report.write_text(json.dumps(
        {"schema": "enkaku_boot_patch_v1", "font_vaddr": KANJI_FONT,
         "glyphs": {str(k): v for k, v in GLYPHS.items()}, "strings": changes},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(data)} bytes -> {args.out}\n-> {args.report}")


if __name__ == "__main__":
    main()

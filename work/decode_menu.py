"""Decode the executable's menu strings with the font the executable actually uses.

The reader at 0x884be84 and the glyph lookup at 0x884bfb8 settle the format:

    one byte 0x28..0x7A      Shift-JIS hiragana, code = 0x8200 | (b + 0x77)
    one byte 0xA7..0xDD      half-width katakana, mapped through a table at 0x88EA394
    two bytes, lead 0x81..0x9F or 0xE0..0xFC   the code is (lead << 8) | trail
    code < 0x8800            drawn from the font at 0x8890F10
    code >= 0x8800           index = (code - 0x8800 >> 8) * 253 + (code & 0xFF),
                             glyph at 0x88EA760 + (index >> 1) * 256

So the kana are ordinary Shift-JIS and the kanji live in a private block starting where
Shift-JIS leaves 0x8800 unassigned.  Nothing here indexes the dialogue font, which is why the
byte pairs looked familiar and the characters never matched.

This prints each string with its kana resolved and its kanji left as indices, and lists the
indices so their glyphs can be rendered and read.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
BOOT = ROOT / "iso_extract" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN"
VADDR_TO_FILE = 0x8803FAC
KANA_TABLE = 0x88EA394


def kana_table(blob: bytes):
    at = KANA_TABLE - VADDR_TO_FILE
    return {0xA7 + i: int.from_bytes(blob[at + i * 2:at + i * 2 + 2], "big")
            for i in range(0xDE - 0xA7)}


def decode(blob: bytes, start: int, table) -> tuple[str, list[int]]:
    out, indices, i = [], [], start
    while i < len(blob) and blob[i]:
        b = blob[i]
        if 0x81 <= b < 0xA0 or 0xE0 <= b < 0xFD:
            code = (b << 8) | blob[i + 1]
            i += 2
        elif 0xA7 <= b < 0xDE:
            code = table[b]
            i += 1
        elif 0x28 <= b < 0x7B:
            code = 0x8200 | (b + 0x77)
            i += 1
        else:
            out.append(f"<{b:02x}>")
            i += 1
            continue
        if code < 0x8800:
            try:
                out.append(code.to_bytes(2, "big").decode("cp932"))
            except UnicodeDecodeError:
                out.append(f"<{code:04x}>")
        else:
            index = ((code - 0x8800) >> 8) * 253 + (code & 0xFF)
            indices.append(index)
            out.append(f"[{index}]")
    return "".join(out), indices


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=BOOT)
    parser.add_argument("--table", type=lambda v: int(v, 0), default=0x8907590,
                        help="virtual address of a string pointer table")
    parser.add_argument("--count", type=int, default=48)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "menu_strings.json")
    args = parser.parse_args()

    blob = args.file.read_bytes()
    table = kana_table(blob)
    at = args.table - VADDR_TO_FILE

    strings, used = [], []
    for n in range(args.count):
        pointer, = struct.unpack_from("<I", blob, at + n * 4)
        offset = pointer - VADDR_TO_FILE
        if not (0 < offset < len(blob) - 2):
            break
        text, indices = decode(blob, offset, table)
        if not text:
            break
        strings.append({"n": n, "vaddr": pointer, "text": text})
        used += indices
        print(f"  [{n:2d}] {pointer:#010x}  {text}")

    order, seen = [], set()
    for i in used:
        if i not in seen:
            seen.add(i)
            order.append(i)
    args.out.write_text(json.dumps({"schema": "enkaku_menu_strings_v1",
                                    "table": args.table, "strings": strings,
                                    "kanji_indices": order},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{len(strings)} strings, {len(order)} distinct kanji indices")
    print(" ".join(str(i) for i in order[:60]))
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

"""Decode a region of BOOT.BIN with the game's own text encoding.

インストール turned up in BOOT.BIN written the way the game writes text -- half-width katakana
at 0xB0..0xD9 -- with 83 66 in front of it, which is Shift-JIS デ.  So the menu strings are
there after all; every earlier search missed them because it looked for Shift-JIS 最初から and
the game stores kanji as an index into its own font instead.

This applies the same reader the script extraction uses: one byte from 0x28 for hiragana,
0xA1..0xDF for half-width katakana, 0x81 and 0x83 leads for Shift-JIS punctuation and kana, and
two bytes from 0x88..0x8D for a font slot.  Strings are NUL-terminated here rather than framed
by the 07 1C ... 12 10 markers the script uses.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
FONT = ROOT / "font_extract"

HIRA_BASE = 0x28
# The script decoder's table starts at あ and the menu came out five kana off -- に read as ば,
# し as ぜ, す as ぞ.  The offset is constant because the game's table also carries the small
# vowels ぁぃぅぇぉ, which the script never needed.  With them in place 「ろをぜえぬぞぐ？」
# resolves to 「よろしいですか？」.
HIRA = ("ぁあぃいぅうぇえぉおかがきぎくぐけげこごさざしじすずせぜそぞただちぢっつづてでとど"
        "なにぬねのはばぱひびぴふぶぷへべぺほぼぽまみむめもゃやゅゆょよらりるれろゎわゐゑをん")
KATA = "。「」、・ヲァィゥェォャュョッーアイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワン゛゜"


def decode(blob: bytes, start: int, end: int, slots: dict[int, str], raw: bool = False):
    out, i = [], start
    while i < end:
        b = blob[i]
        if b == 0x00:
            out.append("\0")
            i += 1
        elif 0x88 <= b <= 0x8D and i + 1 < end:
            index = (b - 0x88) * 253 + blob[i + 1]
            out.append(f"[{index}]" if raw else slots.get(index, f"[{index}]"))
            i += 2
        elif b in (0x81, 0x82, 0x83, 0x84) and i + 1 < end:
            try:
                out.append(bytes(blob[i:i + 2]).decode("cp932"))
            except UnicodeDecodeError:
                out.append(f"<{b:02x}{blob[i + 1]:02x}>")
            i += 2
        elif 0xA1 <= b <= 0xDF:
            out.append(KATA[b - 0xA1] if b - 0xA1 < len(KATA) else "?")
            i += 1
        elif HIRA_BASE <= b < HIRA_BASE + len(HIRA):
            out.append(HIRA[b - HIRA_BASE])
            i += 1
        elif 0x20 <= b < 0x7F:
            out.append(chr(b))
            i += 1
        else:
            out.append(f"<{b:02x}>")
            i += 1
    return "".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path,
                        default=ROOT / "iso_extract" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN")
    parser.add_argument("--start", type=lambda v: int(v, 0), default=0x103700)
    parser.add_argument("--end", type=lambda v: int(v, 0), default=0x103C00)
    parser.add_argument("--min-run", type=int, default=3)
    parser.add_argument("--raw", action="store_true",
                        help="print font slot numbers instead of characters")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "boot_strings.json")
    args = parser.parse_args()

    charmap = json.loads((FONT / "charmap_v5.json").read_text(encoding="utf-8"))["map"]
    slots = {int(k): v for k, v in charmap.items()}

    blob = args.file.read_bytes()
    text = decode(blob, args.start, args.end, slots, raw=args.raw)

    # split on NULs and keep anything with real characters in it
    strings, at = [], args.start
    for piece in text.split("\0"):
        clean = piece.strip()
        if len(clean) >= args.min_run and not clean.startswith("<"):
            strings.append(clean)
    args.out.write_text(json.dumps({"schema": "enkaku_boot_strings_v1",
                                    "file": str(args.file), "start": args.start,
                                    "end": args.end, "strings": strings},
                                   ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{args.file.name} {args.start:#x}..{args.end:#x}\n")
    for s in strings:
        print(f"   {s}")
    print(f"\n{len(strings)} strings -> {args.out}")


if __name__ == "__main__":
    main()

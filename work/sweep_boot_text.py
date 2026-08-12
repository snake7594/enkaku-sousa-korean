"""Sweep BOOT.BIN for text in the game's encoding and score how well the script charmap fits.

The menu block at 0x103700 decodes with perfect kana and wrong kanji: 「上書きしてよろしいですか？」
is written 88 9a 89 51, and glyph 154 of the script font -- which is what 88 9a addresses -- is
帰, not 上.  Either the menu draws from a font nobody has found, or these particular strings are
not the ones the game shows.

Both possibilities are testable in the same sweep.  Run the decoder over the whole binary and
score each block on how much of it lands on kanji the script charmap knows.  A block that
scores well is text the script font really does render; a block that scores badly, like this
one, is addressing something else.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from decode_boot_text import HIRA, HIRA_BASE, KATA, decode

ROOT = Path(r"D:\psp\원격수사")
FONT = ROOT / "font_extract"
BOOT = ROOT / "iso_extract" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN"

COMMON = set("上書存在削除保存記録開始設定終了確認選択画面音量字幕操作説明戻進次前決定"
             "最初続新規読込данные日時場所章話")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=BOOT)
    parser.add_argument("--block", type=int, default=0x400)
    parser.add_argument("--min-kana", type=int, default=24,
                        help="kana in a block before it counts as text at all")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "boot_sweep.json")
    args = parser.parse_args()

    charmap = json.loads((FONT / "charmap_v5.json").read_text(encoding="utf-8"))["map"]
    slots = {int(k): v for k, v in charmap.items()}
    blob = args.file.read_bytes()

    blocks = []
    for start in range(0, len(blob) - args.block, args.block):
        window = blob[start:start + args.block]
        kana = sum(1 for b in window
                   if HIRA_BASE <= b < HIRA_BASE + len(HIRA) or 0xA1 <= b <= 0xDF)
        if kana < args.min_kana:
            continue
        text = decode(blob, start, start + args.block, slots)
        known = sum(1 for ch in text if ch in COMMON)
        unknown = text.count("[")
        blocks.append({"offset": start, "kana": kana, "menu_words": known,
                       "unmapped_slots": unknown,
                       "sample": text.replace("\0", " ")[:90]})

    blocks.sort(key=lambda b: -b["menu_words"])
    args.out.write_text(json.dumps({"schema": "enkaku_boot_sweep_v1",
                                    "blocks": blocks[:80]}, ensure_ascii=False, indent=1),
                        encoding="utf-8")

    print(f"{len(blocks)} blocks of {args.block} bytes carry enough kana to be text\n")
    for b in blocks[:14]:
        print(f"   {b['offset']:#010x}  kana {b['kana']:3d}  menu words {b['menu_words']:2d}  "
              f"unmapped {b['unmapped_slots']:2d}")
        print(f"      {b['sample']}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

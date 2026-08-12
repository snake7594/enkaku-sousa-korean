"""Find the table that turns the menu's kanji indices into real characters.

The menu strings in BOOT.BIN are written in the game's encoding, and the kana come out
perfectly, but the kanji do not.  「すでにインストールデータが[245][246]します。」 has to be
存在, and slot 245 of the script font is 妻 -- I read that glyph myself.  存 and 在 sit at 183
and 143 in that font, nowhere near each other, while the menu wants them adjacent.  So the
menu is not indexing the script font at all.

The likely shape is a lookup table: the menu stores a small index, the game reads a Shift-JIS
code out of an array, and hands that to the renderer.  Such a table is a long run of u16 values
that are all valid Shift-JIS kanji, which is rare enough in a binary to find by scanning.

If the table exists, entry 245 is 存 and entry 246 is 在, and that check either confirms it or
kills it outright.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
BOOT = ROOT / "iso_extract" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN"

# what the decoded menu says each index must be
EXPECT = {245: "存", 246: "在", 154: "上", 334: "書"}


def is_sjis_kanji(code: int) -> bool:
    lead, trail = code >> 8, code & 0xFF
    if not (0x88 <= lead <= 0x9F or 0xE0 <= lead <= 0xEA):
        return False
    return (0x40 <= trail <= 0x7E) or (0x80 <= trail <= 0xFC)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=BOOT)
    parser.add_argument("--min-run", type=int, default=200)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "kanji_table.json")
    args = parser.parse_args()

    blob = args.file.read_bytes()
    runs = []
    for order in ("little", "big"):
        start, n = None, len(blob) - 1
        for i in range(0, n, 2):
            code = int.from_bytes(blob[i:i + 2], order)
            if is_sjis_kanji(code):
                if start is None:
                    start = i
            else:
                if start is not None and (i - start) // 2 >= args.min_run:
                    runs.append({"order": order, "offset": start,
                                 "entries": (i - start) // 2})
                start = None
        if start is not None and (n - start) // 2 >= args.min_run:
            runs.append({"order": order, "offset": start, "entries": (n - start) // 2})

    checked = []
    for run in runs:
        order, base = run["order"], run["offset"]
        verdict = {}
        for index, want in EXPECT.items():
            at = base + index * 2
            if at + 2 > len(blob):
                verdict[index] = None
                continue
            code = int.from_bytes(blob[at:at + 2], order)
            try:
                got = code.to_bytes(2, "big").decode("cp932")
            except UnicodeDecodeError:
                got = "?"
            verdict[index] = got
        run["check"] = verdict
        run["matches"] = sum(1 for k, v in verdict.items() if v == EXPECT[k])
        checked.append(run)

    checked.sort(key=lambda r: (-r["matches"], -r["entries"]))
    args.out.write_text(json.dumps({"schema": "enkaku_kanji_table_v1",
                                    "expect": EXPECT, "runs": checked[:40]},
                                   ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(runs)} runs of {args.min_run}+ consecutive Shift-JIS kanji in {args.file.name}\n")
    for run in checked[:12]:
        shown = ", ".join(f"{k}->{v}" for k, v in run["check"].items())
        print(f"   {run['order']:6s} {run['offset']:#010x}  {run['entries']:5d} entries  "
              f"matches {run['matches']}/4   {shown}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

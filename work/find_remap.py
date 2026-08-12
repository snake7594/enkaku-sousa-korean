"""Look for a table that maps the menu's kanji indices onto script-font slots.

The menu writes 存在 as indices 245 and 246.  In the script font those characters are at slots
183 and 143 -- I rendered 245 and 246 to be sure, and they are 妻 and 赤, so the menu is not
addressing that font directly.  There is no index-to-Shift-JIS table in BOOT.BIN either.

What is left is indirection: the menu index is a position in a table, and the table holds the
font slot.  That is a claim with four independent predictions, because four menu indices have
known answers -- 245 must give 183, 246 must give 143, 154 must give 170, 334 must give 190.
A table satisfying all four by chance is not plausible, and one satisfying none kills the idea.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
ISO = ROOT / "iso_extract"

# menu index -> script font slot, read off the decoded strings and the rendered glyphs
WANT = {245: 183, 246: 143, 154: 170, 334: 190}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", nargs="*", default=[
        "PSP_GAME/SYSDIR/BOOT.BIN", "PSP_GAME/USRDIR/0001", "PSP_GAME/USRDIR/0004",
        "PSP_GAME/USRDIR/0011"])
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "remap_scan.json")
    args = parser.parse_args()

    hits = []
    for rel in args.files:
        path = ISO / rel
        if not path.exists():
            continue
        blob = path.read_bytes()
        for width, order in ((2, "little"), (2, "big"), (1, None)):
            span = max(WANT) * width + width
            for base in range(0, len(blob) - span):
                ok = True
                for index, slot in WANT.items():
                    at = base + index * width
                    value = (blob[at] if width == 1
                             else int.from_bytes(blob[at:at + width], order))
                    if value != slot:
                        ok = False
                        break
                if ok:
                    hits.append({"file": rel, "base": base, "width": width,
                                 "order": order or "n/a"})
        print(f"{rel:34s} scanned {len(blob):>10d} bytes")

    args.out.write_text(json.dumps({"schema": "enkaku_remap_scan_v1",
                                    "want": {str(k): v for k, v in WANT.items()},
                                    "hits": hits}, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"\n{len(hits)} tables satisfy all four predictions")
    for h in hits[:10]:
        print(f"   {h['file']}  base {h['base']:#010x}  {h['width']}-byte {h['order']}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

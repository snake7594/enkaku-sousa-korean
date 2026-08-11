"""Pin the kana table's base index using kana we already know the codes for.

Frequency analysis of the script established several code→kana pairs beyond doubt
(0x2B=い, 0x32=か, 0x3E=し, 0x55=の, 0x7A=ん and more).  For a candidate base B, the
glyphs at B+(code-0x28) must therefore read as exactly those kana — a much sharper
test than correlating a whole gojūon sequence against a different typeface.

Each candidate base is drawn as one row so the right one can be recognised at a glance.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

import font as fontlib

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")
BASE_ADDR = 0x92060

# codes whose kana are settled by how often they appear in the script
KNOWN = [(0x2B, "い"), (0x32, "か"), (0x3E, "し"), (0x46, "た"), (0x4D, "て"),
         (0x51, "な"), (0x55, "の"), (0x4A, "っ"), (0x7A, "ん"), (0x4E, "で"),
         (0x33, "が"), (0x4F, "と")]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--addr", type=lambda v: int(v, 0), default=BASE_ADDR)
    parser.add_argument("--from", dest="lo", type=int, default=0)
    parser.add_argument("--to", dest="hi", type=int, default=32)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    glyphs = fontlib.tiles_to_glyphs(BOOT.read_bytes(), args.addr, 140)
    rows = []
    labels = []
    for base in range(args.lo, args.hi):
        picks = [base + (code - 0x28) for code, _ in KNOWN]
        if max(picks) >= len(glyphs):
            break
        rows.append(np.concatenate([glyphs[p] for p in picks], axis=1) * 17)
        labels.append(base)

    if not rows:
        print("nothing to show")
        return
    height = len(rows) * 18
    width = rows[0].shape[1]
    sheet = np.zeros((height, width), dtype=np.uint8)
    for i, row in enumerate(rows):
        sheet[i * 18 : i * 18 + 16, :] = row.astype(np.uint8)
    Image.fromarray(sheet, "L").resize((width * 4, height * 4), Image.NEAREST).save(args.out)

    print("expected reading for the correct base row: " + "".join(k for _, k in KNOWN))
    print("rows, top to bottom, are bases: " + ", ".join(str(b) for b in labels))
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

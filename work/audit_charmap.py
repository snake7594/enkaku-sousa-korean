"""Put every much-used glyph next to the character the map claims it is.

The glyph-image pass covered the slots that were flagged as duplicates.  Everything else still
rests on context guessing, and slot 432 shows what that is worth: the ledger called it 月, so
the lawyer's name came out 水無月月司, which is not a name.  Rendered, the glyph is plainly 幸
-- 水無月幸司 -- and the 7 occurrences of 幸せ agree.

Nothing here decides anything.  It draws the game's glyph on the left and the claimed
character on the right in a system font, at a size where a wrong claim is obvious, and leaves
the reading to a person.  Slots already read from the image are skipped.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import font as fontlib

ROOT = Path(r"D:\psp\원격수사")
FONT = ROOT / "font_extract"
STREAM = FONT / "script_stream.bin"
JP = Path(r"C:\Windows\Fonts\msgothic.ttc")
LABEL = Path(r"C:\Windows\Fonts\consola.ttf")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-uses", type=int, default=20)
    parser.add_argument("--max-uses", type=int, default=10 ** 9,
                        help="upper bound, to skip a band already checked")
    parser.add_argument("--page", type=int, default=0, help="which page to render")
    parser.add_argument("--per-page", type=int, default=48)
    parser.add_argument("--cols", type=int, default=6)
    parser.add_argument("--scale", type=int, default=3)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    quality = json.loads((FONT / "charmap_quality_corrected.json").read_text(encoding="utf-8"))
    done = {int(e["index"]) for e in quality if e.get("source") == "glyph_image_reading"}
    audit_path = FONT / "charmap_glyph_audit.json"
    audited = {}
    if audit_path.exists():
        for entry in json.loads(audit_path.read_text(encoding="utf-8"))["readings"]:
            audited[int(entry["slot"])] = entry["char"]
    todo = [e for e in quality
            if int(e["index"]) not in done and int(e["index"]) not in audited
            and args.min_uses <= e.get("uses", 0) <= args.max_uses]
    todo.sort(key=lambda e: -e.get("uses", 0))
    pages = (len(todo) + args.per_page - 1) // args.per_page
    chunk = todo[args.page * args.per_page:(args.page + 1) * args.per_page]
    out = args.out or ROOT / "build" / f"charmap_audit_p{args.page}.png"

    glyphs = fontlib.tiles_to_glyphs(STREAM.read_bytes(), 0x80, 684)
    jp = ImageFont.truetype(str(JP), 16 * args.scale - 6)
    small = ImageFont.truetype(str(LABEL), 13)

    cell_w = 16 * args.scale * 2 + 54
    cell_h = 16 * args.scale + 16
    rows = (len(chunk) + args.cols - 1) // args.cols
    sheet = Image.new("RGB", (args.cols * cell_w + 8, rows * cell_h + 8), (16, 16, 16))
    draw = ImageDraw.Draw(sheet)

    for n, entry in enumerate(chunk):
        r, c = divmod(n, args.cols)
        x, y = 8 + c * cell_w, 8 + r * cell_h
        slot = int(entry["index"])
        tile = (glyphs[slot] * 17).astype(np.uint8) if slot < len(glyphs) else None
        if tile is not None:
            img = Image.fromarray(tile, "L").resize(
                (16 * args.scale, 16 * args.scale), Image.NEAREST)
            sheet.paste(img.convert("RGB"), (x + 48, y))
        draw.text((x, y + 6), f"{slot}", font=small, fill=(255, 200, 80))
        draw.text((x, y + 24), f"{entry.get('uses', 0)}", font=small, fill=(110, 110, 110))
        draw.text((x + 48 + 16 * args.scale + 4, y + 2), entry["char"], font=jp,
                  fill=(120, 190, 255))

    sheet.save(out)
    print(f"{len(todo)} slots never read from the image, {args.min_uses}+ uses "
          f"-- page {args.page + 1} of {pages}")
    print("   left: game glyph   right: what the map claims")
    print(f"-> {out} {sheet.size}")


if __name__ == "__main__":
    main()

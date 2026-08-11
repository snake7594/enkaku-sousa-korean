"""Set the newspaper headlines in Korean, vertically, without erasing the character.

These pages are a scene, not a label: the print runs top to bottom in columns about sixteen
pixels wide, and a character sprite is painted over part of it.  So two things have to hold.
The Korean has to be set vertically in the same columns, and it must not spill over the
person standing in front of the page.

The sprite is far darker than either the paper or the print -- luma under 35 against paper at
about 68 -- so it can be masked by value, and every write is made only where that mask is
clear.  The result is that the Korean disappears behind the character exactly where the
Japanese did, including mid-character.

Columns are given right to left, which is the order the page reads in.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import texenc
import texpack

ROOT = Path(r"D:\psp\원격수사")
SERIF = Path(r"C:\Windows\Fonts\HANBatangB.ttf")


def render_column(canvas: Image.Image, box, text: str, font_path: Path, ink) -> int:
    """Draw text down a column, sized so it fills the height the Japanese filled."""
    x0, y0, x1, y1 = box
    width, height = x1 - x0 + 1, y1 - y0 + 1
    if not text:
        return 0
    # A space costs a fraction of a cell rather than a whole one.  Giving it a full cell, as a
    # first attempt did, spent a fifth of the column on nothing and forced the type down to
    # 11px against the 15px the Japanese was set in -- the headline came out visibly smaller
    # than the one it replaced.  Vertical Japanese has no word spaces to compete with.
    weights = [0.34 if not c.strip() else 1.0 for c in text]
    unit = height / sum(weights)
    size = max(6, int(min(width, unit) + 1))
    draw = ImageDraw.Draw(canvas)
    while size > 5:
        font = ImageFont.truetype(str(font_path), size)
        widest = max((draw.textbbox((0, 0), c, font=font)[2] for c in text if c.strip()),
                     default=0)
        if widest <= width:
            break
        size -= 1
    font = ImageFont.truetype(str(font_path), size)
    at = 0.0
    for ch, weight in zip(text, weights):
        if ch.strip():
            b = draw.textbbox((0, 0), ch, font=font)
            cx = x0 + (width - (b[2] - b[0])) / 2 - b[0]
            cy = y0 + at * unit + (weight * unit - (b[3] - b[1])) / 2 - b[1]
            draw.text((cx, cy), ch, font=font, fill=ink)
        at += weight
    return size


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "work" / "newspaper_text.json")
    parser.add_argument("--clean", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0_ko6.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "stream0_ko7.bin")
    parser.add_argument("--font", type=Path, default=SERIF)
    parser.add_argument("--sprite-below", type=int, default=35)
    parser.add_argument("--preview", type=Path, default=ROOT / "build" / "newspaper_ko.png")
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "newspaper_report.json")
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    data = bytearray(args.stream.read_bytes())
    textures = {t.index: t for t in texpack.load_textures(args.clean.read_bytes())}
    shots, done = [], []

    for page in config["pages"]:
        tex = textures[page["index"]]
        original = texpack.decode(tex).convert("RGBA")
        px = np.asarray(original).astype(np.int32)
        luma = px[:, :, :3].mean(axis=2)
        sprite = luma < args.sprite_below

        # paper and print are sampled from the page itself, away from the sprite
        page_only = luma[~sprite]
        paper_luma = float(np.percentile(page_only, 88))
        paper_px = px[(luma >= paper_luma - 2) & (luma <= paper_luma + 2)]
        paper = tuple(int(v) for v in np.median(paper_px, axis=0))
        print_px = px[(luma >= args.sprite_below) & (luma < paper_luma - 12)]
        ink = tuple(int(v) for v in np.percentile(print_px, 8, axis=0))
        ink = ink[:3] + (255,)

        canvas = original.copy()
        draw = ImageDraw.Draw(canvas)
        sizes = []
        for column in page["columns"]:
            box = (column["x0"], column["y0"], column["x1"], column["y1"])
            draw.rectangle(box, fill=paper)
            sizes.append(render_column(canvas, box, column["ko"], args.font, ink))

        # put the character back over the type, so the Korean is hidden exactly where the
        # Japanese was hidden
        merged = np.asarray(canvas).copy()
        merged[sprite] = px[sprite]
        canvas = Image.fromarray(merged.astype(np.uint8), "RGBA")

        indices = texenc.quantise(canvas, tex.palette)
        blob = texenc.encode_indices(tex, indices)
        record = tex.index * 2 + 2
        offset = int.from_bytes(data[record * 4:record * 4 + 4], "little")
        if len(blob) != len(tex.image):
            print(f"   tex{tex.index:04d}: size changed, skipped")
            continue
        data[offset:offset + len(blob)] = blob
        done.append({"index": tex.index, "columns": len(page["columns"]),
                     "paper": list(paper), "ink": list(ink), "sizes_px": sizes})
        shots.append((original, canvas))
        print(f"   tex{tex.index:04d}  {len(page['columns'])} columns, "
              f"{sizes} px, paper {paper}, ink {ink}")

    args.out.write_bytes(bytes(data))
    args.report.write_text(json.dumps({"schema": "enkaku_newspaper_v1", "pages": done},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
    if shots:
        w, h = shots[0][0].size
        sheet = Image.new("RGB", (w, h * 2 * len(shots) + 8 * len(shots)), (18, 18, 18))
        for n, (before, after) in enumerate(shots):
            sheet.paste(before.convert("RGB"), (0, n * (2 * h + 8)))
            sheet.paste(after.convert("RGB"), (0, n * (2 * h + 8) + h + 4))
        sheet = sheet.point(lambda v: min(255, int(v * 2.6)))
        sheet.save(args.preview)
    print(f"\n{len(done)} pages -> {args.out}\n-> {args.preview}")


if __name__ == "__main__":
    main()

"""Measure the column grid of the newspaper textures before drawing anything into them.

These are not labels with a box round them.  They are a page of vertical Japanese set in
columns roughly ten pixels wide, with a character sprite painted over part of it, so the only
way to put Korean back in the same shape is to find where the ink actually sits.

Columns run top to bottom and are separated by gaps, so a vertical ink profile finds them.
The sprite is solid and much darker than the paper, so it is excluded first -- otherwise its
silhouette reads as one enormous column and swallows the grid.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import texpack

ROOT = Path(r"D:\psp\원격수사")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=int, default=433)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--sprite-below", type=int, default=35,
                        help="luma under this is the character sprite, not print")
    parser.add_argument("--ink-below", type=int, default=56,
                        help="luma between sprite-below and this is print")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    out = args.out or ROOT / "build" / f"paper{args.index}_grid.png"
    report = args.report or ROOT / "build" / f"paper{args.index}_grid.json"

    textures = {t.index: t for t in texpack.load_textures(args.stream.read_bytes())}
    tex = textures[args.index]
    image = texpack.decode(tex).convert("RGB")
    px = np.asarray(image).astype(np.int32)
    luma = px.mean(axis=2)

    # The page has three levels, not two: paper at luma 69, print between about 45 and 64, and
    # the character sprite far below at 12 to 24.  Treating anything dark as ink makes the
    # sprite the widest column on the page and hides the grid entirely, so the sprite is cut
    # off by value rather than by how much of a column it fills.
    paper = float(np.percentile(luma, 90))
    sprite_mask = luma < args.sprite_below
    ink = (luma >= args.sprite_below) & (luma < args.ink_below)
    sprite = sprite_mask.mean(axis=0) > 0.5

    profile = ink.sum(axis=0)
    columns, start = [], None
    for x in range(len(profile) + 1):
        on = x < len(profile) and profile[x] > 0
        if on and start is None:
            start = x
        elif not on and start is not None:
            if x - start >= 2:
                rows = np.nonzero(ink[:, start:x].any(axis=1))[0]
                columns.append({"x0": start, "x1": x - 1, "width": x - start,
                                "y0": int(rows.min()), "y1": int(rows.max())})
            start = None

    widths = [c["width"] for c in columns]
    report.write_text(json.dumps(
        {"schema": "enkaku_paper_grid_v1", "index": args.index,
         "size": [tex.width, tex.height], "paper_luma": paper,
         "sprite_columns": int(sprite.sum()), "columns": columns},
        ensure_ascii=False, indent=1), encoding="utf-8")

    canvas = image.convert("RGBA").resize((tex.width * 2, tex.height * 2), Image.NEAREST)
    draw = ImageDraw.Draw(canvas)
    for n, c in enumerate(columns):
        draw.rectangle((c["x0"] * 2, c["y0"] * 2, c["x1"] * 2 + 1, c["y1"] * 2 + 1),
                       outline=(255, 90, 90, 255) if n % 2 else (90, 190, 255, 255))
    canvas.save(out)

    print(f"tex{args.index:04d} {tex.width}x{tex.height}, paper luma {paper:.0f}, "
          f"{int(sprite.sum())} columns covered by the sprite")
    print(f"{len(columns)} ink columns; widths "
          f"{sorted(set(widths))[:12]}")
    for c in columns[:8]:
        print(f"   x {c['x0']:3d}..{c['x1']:3d} (w{c['width']:2d})  y {c['y0']:3d}..{c['y1']:3d}")
    print(f"-> {out}\n-> {report}")


if __name__ == "__main__":
    main()

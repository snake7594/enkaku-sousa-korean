"""Show a newspaper texture magnified with a coordinate grid, to read boxes off by eye.

Automatic column detection keeps missing here.  The two pages have different paper values, the
character sprite sits on top of the print, and the headlines are set in columns two and three
times the body width, so one threshold either merges the whole page into a single block or
splits a headline into its strokes.

There are only six headlines across both pages, so measuring them by eye off a ruled image is
both quicker and more certain than tuning a detector until it agrees.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import texpack

ROOT = Path(r"D:\psp\원격수사")
LABEL = Path(r"C:\Windows\Fonts\consola.ttf")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=int, default=433)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--scale", type=int, default=3)
    parser.add_argument("--step", type=int, default=16, help="grid spacing in texture pixels")
    parser.add_argument("--crop", type=str, default="", help="x0,y0,x1,y1 in texture pixels")
    parser.add_argument("--brighten", type=float, default=2.6)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    out = args.out or ROOT / "build" / f"paper{args.index}_ruler.png"
    textures = {t.index: t for t in texpack.load_textures(args.stream.read_bytes())}
    tex = textures[args.index]
    image = texpack.decode(tex).convert("RGB")

    ox, oy = 0, 0
    if args.crop:
        x0, y0, x1, y1 = (int(v) for v in args.crop.split(","))
        image = image.crop((x0, y0, x1, y1))
        ox, oy = x0, y0

    # the page is printed dark on dark; lifting it makes the columns readable on screen
    image = image.point(lambda v: min(255, int(v * args.brighten)))
    w, h = image.size
    canvas = image.resize((w * args.scale, h * args.scale), Image.LANCZOS).convert("RGB")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(str(LABEL), 12)

    for x in range(0, w + 1, args.step):
        major = (x + ox) % (args.step * 4) == 0
        draw.line((x * args.scale, 0, x * args.scale, h * args.scale),
                  fill=(255, 70, 70) if major else (70, 110, 200), width=1)
        if major:
            draw.text((x * args.scale + 2, 2), str(x + ox), font=font, fill=(255, 220, 90))
    for y in range(0, h + 1, args.step):
        major = (y + oy) % (args.step * 4) == 0
        draw.line((0, y * args.scale, w * args.scale, y * args.scale),
                  fill=(255, 70, 70) if major else (70, 110, 200), width=1)
        if major:
            draw.text((2, y * args.scale + 2), str(y + oy), font=font, fill=(255, 220, 90))

    canvas.save(out)
    print(f"tex{args.index:04d} {tex.width}x{tex.height}, showing "
          f"{ox},{oy} .. {ox + w},{oy + h} at {args.scale}x, grid every {args.step}px")
    print(f"-> {out} {canvas.size}")


if __name__ == "__main__":
    main()

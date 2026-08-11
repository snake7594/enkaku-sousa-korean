"""Render an atlas row magnified with a pixel ruler, so merged runs can be split by eye.

Gap detection separates words only where the glyphs do not touch.  In rows 2 and 3 they do,
and 次へ辞典Ｒ comes back as one 78-pixel run -- painting into that would erase whatever
shares it.  The isolated words give the pitch though (メニュー is 62px for four characters,
so ~15.5 each), which means the boundaries inside a merged run are predictable and only need
confirming.

The ruler makes that confirmation possible: ticks every 8 texture pixels, labelled every 16,
against the magnified row.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import texpack

ROOT = Path(r"D:\psp\원격수사")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=int, default=409)
    parser.add_argument("--pitch", type=int, default=16)
    parser.add_argument("--scale", type=int, default=6)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "atlas_ruler.png")
    args = parser.parse_args()

    data = args.stream.read_bytes()
    tex = next(t for t in texpack.load_textures(data) if t.index == args.index)
    image = texpack.decode(tex).convert("RGBA")
    rows = tex.height // args.pitch
    s = args.scale
    ruler_h = 18

    sheet = Image.new("RGBA", (tex.width * s, rows * (args.pitch * s + ruler_h + 6)),
                      (16, 16, 16, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 11)

    for r in range(rows):
        y0 = r * (args.pitch * s + ruler_h + 6)
        band = image.crop((0, r * args.pitch, tex.width, (r + 1) * args.pitch))
        sheet.paste(band.resize((tex.width * s, args.pitch * s), Image.NEAREST), (0, y0))
        ty = y0 + args.pitch * s
        for x in range(0, tex.width + 1, 8):
            tall = x % 32 == 0
            draw.line((x * s, ty, x * s, ty + (12 if tall else 6)),
                      fill=(120, 200, 255, 255) if tall else (80, 80, 80, 255))
            if tall:
                draw.text((x * s + 2, ty + 4), str(x), font=font, fill=(120, 200, 255, 255))
        draw.text((4, y0 + 2), f"row {r}", font=font, fill=(255, 220, 120, 255))

    sheet.save(args.out)
    print(f"tex{tex.index:04d} {tex.width}x{tex.height}, {rows} rows -> {args.out}")


if __name__ == "__main__":
    main()

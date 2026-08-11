"""Locate the character name plates among the 128x128 textures.

The contact sheet shows the last two rows carrying names -- 吉本ユミ, 近藤克美, 三浦正信 and
so on -- painted across the bottom of a portrait.  A first attempt filtered on "solid opaque
bottom strip" and matched nothing, because the name sits on the artwork rather than on a
band of its own.

So this looks for what the plates actually have: a narrow horizontal run of high-contrast
ink near the bottom edge, the shape text makes against a photograph.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import texpack

ROOT = Path(r"D:\psp\원격수사")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--band", type=int, default=26, help="pixels from the bottom")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "nameplates.png")
    args = parser.parse_args()

    data = args.stream.read_bytes()
    group = [t for t in texpack.load_textures(data) if (t.width, t.height) == (128, 128)]
    print(f"{len(group)} textures of 128x128")

    scored = []
    for tex in group:
        px = np.asarray(texpack.decode(tex).convert("RGBA")).astype(np.int32)
        band = px[128 - args.band:, :, :]
        luma = band[:, :, :3].mean(axis=2)
        opaque = band[:, :, 3] > 40
        if opaque.mean() < 0.5:
            continue
        floor = float(np.median(luma[opaque]))
        ink = (np.abs(luma - floor) > 60) & opaque
        rows = ink.sum(axis=1)
        # text is a few bright rows, not the whole band
        busy = (rows > 6).sum()
        if 4 <= busy <= args.band - 4 and ink.mean() > 0.03:
            scored.append((ink.mean(), tex))

    scored.sort(key=lambda s: -s[0])
    picked = [t for _, t in scored[:32]]
    print(f"{len(picked)} candidates with a text-shaped band near the bottom")

    font = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 14)
    cols, sc, lw = 4, 3, 46
    rows_n = (len(picked) + cols - 1) // cols
    sheet = Image.new("RGBA",
                      (cols * (128 * sc + lw + 6) + 6,
                       rows_n * (args.band * sc + 8) + 6), (18, 18, 18, 255))
    draw = ImageDraw.Draw(sheet)
    for n, tex in enumerate(picked):
        r, c = divmod(n, cols)
        x = 6 + c * (128 * sc + lw + 6)
        y = 6 + r * (args.band * sc + 8)
        draw.text((x, y + 16), str(tex.index), font=font, fill=(255, 200, 80, 255))
        crop = texpack.decode(tex).crop((0, 128 - args.band, 128, 128))
        sheet.paste(crop.resize((128 * sc, args.band * sc), Image.NEAREST), (x + lw, y))
    sheet.save(args.out)
    print(f"-> {args.out} {sheet.size}")


if __name__ == "__main__":
    main()

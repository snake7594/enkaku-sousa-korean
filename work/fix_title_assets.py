"""Patch the title logo and the 辞典/解説 buttons.

Both are small fixed-size textures, so the usual rule holds: keep the artwork, repaint only
the text, sample the colours from the image.

The logo is the one place where matching the original exactly is not possible -- 遠隔捜査 is
set in a display face with 捜査 picked out in red, and Korean has no equivalent glyph
shapes.  It is rendered in the same two colours and the same red/white split (원격 white,
수사 red) so the identity of the mark survives, and the tagline underneath is translated.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import texenc
import texpack

ROOT = Path(r"D:\psp\원격수사")
BOLD = Path(r"C:\Windows\Fonts\HANBatangB.ttf")


def write_back(data: bytearray, tex, canvas: Image.Image) -> bool:
    indices = texenc.quantise(canvas, tex.palette)
    blob = texenc.encode_indices(tex, indices)
    record = tex.index * 2 + 2
    offset = int.from_bytes(data[record * 4:record * 4 + 4], "little")
    if len(blob) != len(tex.image):
        return False
    data[offset:offset + len(blob)] = blob
    return True


def centred(draw, text, font, box):
    b = draw.textbbox((0, 0), text, font=font)
    return ((box[0] + box[2]) / 2 - (b[2] + b[0]) / 2,
            (box[1] + box[3]) / 2 - (b[3] + b[1]) / 2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0_ko2.bin")
    parser.add_argument("--clean", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "stream0_ko2.bin")
    parser.add_argument("--preview", type=Path, default=ROOT / "build" / "title_ko.png")
    args = parser.parse_args()

    data = bytearray(args.stream.read_bytes())
    clean = args.clean.read_bytes()
    textures = {t.index: t for t in texpack.load_textures(clean)}
    previews = []

    # --- title logo -------------------------------------------------------
    tex = textures[251]
    original = texpack.decode(tex).convert("RGBA")
    px = np.asarray(original).astype(np.int32)
    # the red of 捜査 and the white of 遠隔, taken from the artwork
    rgb = px[:, :, :3]
    reddish = (rgb[:, :, 0] > 120) & (rgb[:, :, 0] > rgb[:, :, 2] + 60)
    red = tuple(int(v) for v in np.median(px[reddish], axis=0)) if reddish.any() \
        else (200, 30, 30, 255)
    # only pixels that are actually painted: the median over "bright" alone included fully
    # transparent ones and produced white with alpha 0, which drew nothing
    solid = px[(rgb.mean(axis=2) > 200) & (px[:, :, 3] > 200)]
    white = tuple(int(v) for v in np.median(solid, axis=0)) if len(solid) \
        else (245, 245, 245, 255)
    red = red[:3] + (255,)
    print(f"logo tex0251 {tex.width}x{tex.height}: white {white}, red {red}")

    canvas = Image.new("RGBA", (tex.width, tex.height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(str(BOLD), 30)
    left, right = "원격", "수사"
    wl = draw.textlength(left, font=font)
    wr = draw.textlength(right, font=font)
    x = (tex.width - (wl + wr)) / 2
    y = 6
    draw.text((x, y), left, font=font, fill=white)
    draw.text((x + wl, y), right, font=font, fill=red)
    tag = ImageFont.truetype(str(BOLD), 11)
    line = "진실을 향한 23일간"
    tw = draw.textlength(line, font=tag)
    draw.text(((tex.width - tw) / 2, y + 34), line, font=tag, fill=white)
    if not write_back(data, tex, canvas):
        print("   logo: size changed, skipped")
    else:
        previews.append((original, canvas))

    # --- 辞典 / 解説 buttons ----------------------------------------------
    tex = textures[400]
    original = texpack.decode(tex).convert("RGBA")
    px = np.asarray(original).astype(np.int32)
    canvas = original.copy()
    draw = ImageDraw.Draw(canvas)
    half = tex.width // 2
    # four cells: two states stacked, two buttons side by side
    cells = [((4, 2, half - 4, 30), "사전"), ((half + 4, 2, tex.width - 4, 30), "해설"),
             ((4, 34, half - 4, 62), "사전"), ((half + 4, 34, tex.width - 4, 62), "해설")]
    font = ImageFont.truetype(str(BOLD), 17)
    for box, text in cells:
        # Sample the corner rather than the middle: the middle is where the Japanese is, and
        # a median taken across it produced a fill too close to the ink to cover anything.
        corner = px[box[1] + 1:box[1] + 5, box[0] + 1:box[0] + 5].reshape(-1, 4)
        back = tuple(int(v) for v in np.median(corner, axis=0))
        ink = (20, 20, 20, 255) if sum(back[:3]) > 330 else (245, 245, 245, 255)
        draw.rectangle(box, fill=back)
        draw.text(centred(draw, text, font, box), text, font=font, fill=ink)
    if not write_back(data, tex, canvas):
        print("   buttons: size changed, skipped")
    else:
        previews.append((original, canvas))
        print(f"buttons tex0400 {tex.width}x{tex.height}: patched")

    args.out.write_bytes(bytes(data))

    pad = 6
    w = max(o.width for o, _ in previews)
    h = sum(o.height * 2 + pad * 2 for o, _ in previews)
    sheet = Image.new("RGBA", (w + pad * 2, h + pad), (24, 24, 24, 255))
    y = pad
    for original, canvas in previews:
        sheet.paste(original, (pad, y), original)
        y += original.height + pad
        sheet.paste(canvas, (pad, y), canvas)
        y += canvas.height + pad
    sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST).save(args.preview)
    print(f"-> {args.out}\n-> {args.preview}")


if __name__ == "__main__":
    main()

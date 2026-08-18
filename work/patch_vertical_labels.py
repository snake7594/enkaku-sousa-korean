"""The three relationship labels set vertically, and the second business card.

Every relationship label exists twice: once horizontal and once vertical.  The horizontal set
was translated long ago -- 고교 동창, 수사 협력, 선배와 후배 -- and the vertical twins were never
touched, so the same relation reads Korean in one place and Japanese in another.  The wording
here is taken from the horizontal twin rather than translated afresh, so the pair agrees.

Vertical means one character per line, which the horizontal label patcher cannot do, hence a
separate pass.  The card is a different job again: its front is fully Korean and only the
second card behind it still carries 株式会社 down its edge, at a slight tilt.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import texenc
import texpack

ROOT = Path(r"D:\psp\원격수사")
SERIF = Path(r"C:\Windows\Fonts\HANBatangB.ttf")

# index -> (japanese, korean, the horizontal twin the wording comes from)
VERTICAL = {
    390: ("高校の同級生", "고교 동창", 379),
    392: ("捜査協力", "수사 협력", 381),
    393: ("先輩と後輩", "선배와 후배", 382),
}


def ink_box(image: Image.Image):
    """Where the type sits.  These labels float on nothing, so the ground is transparent."""
    px = np.asarray(image).astype(int)
    drawn = px[:, :, 3] > 24
    if not drawn.any():
        return None
    ys, xs = np.nonzero(drawn)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def set_vertical(image: Image.Image, korean: str, font_path: Path) -> Image.Image:
    box = ink_box(image)
    if box is None:
        raise SystemExit("no ink found")
    out = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(out)

    chars = [c for c in korean if c != " "]
    width = box[2] - box[0] + 1
    height = box[3] - box[1] + 1
    # Leave a little air between characters -- the Japanese is a narrow face and Korean is
    # square, so sizing purely by the slot height runs the glyphs into each other.
    step = height / len(chars)
    size = int(min(width - 2, step - 3))
    font = ImageFont.truetype(str(font_path), max(8, size))
    cx = (box[0] + box[2]) / 2
    for i, ch in enumerate(chars):
        b = draw.textbbox((0, 0), ch, font=font)
        x = cx - (b[2] - b[0]) / 2 - b[0]
        y = box[1] + step * i + (step - (b[3] - b[1])) / 2 - b[1]
        # white with a dark rim, the way the original is set
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    draw.text((x + dx, y + dy), ch, font=font, fill=(20, 20, 20, 255))
        draw.text((x, y), ch, font=font, fill=(255, 255, 255, 255))
    return out


def set_card(image: Image.Image, font_path: Path) -> Image.Image:
    """The back card's 株式会社, running down its right edge on a tilt."""
    px = np.asarray(image).astype(int)
    # the strip is dark type on the pale card, in the top-right corner
    region = (104, 8, 122, 60)
    patch = px[region[1]:region[3], region[0]:region[2]]
    luma = patch[:, :, :3].mean(axis=2)
    ink = luma < 110
    if not ink.any():
        raise SystemExit("tex263: no dark type found in the card strip")
    back = tuple(int(v) for v in np.median(patch[~ink], axis=0))
    ink_colour = tuple(int(v) for v in patch[ink].mean(axis=0))[:3] + (255,)

    out = image.copy()
    draw = ImageDraw.Draw(out)
    draw.rectangle(region, fill=back)
    layer = Image.new("RGBA", (60, 120), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    font = ImageFont.truetype(str(font_path), 9)
    for i, ch in enumerate("주식회사"):
        b = ld.textbbox((0, 0), ch, font=font)
        ld.text((30 - (b[2] - b[0]) / 2 - b[0], 6 + i * 10 - b[1]), ch, font=font,
                fill=ink_colour)
    layer = layer.rotate(-6, resample=Image.BICUBIC, center=(30, 60))
    out.alpha_composite(layer, (region[0] - 21, region[1] - 6))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--clean", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--font", type=Path, default=SERIF)
    parser.add_argument("--preview", type=Path, default=ROOT / "build" / "vertical_ko.png")
    args = parser.parse_args()

    data = bytearray(args.stream.read_bytes())
    # Decode from the stream being patched, not from the pristine one.  The card's front face
    # is already Korean in the released build, and reading the picture from the original would
    # put the Japanese back while fixing the strip behind it.
    current = {t.index: t for t in texpack.load_textures(bytes(data))}
    pristine = {t.index: t for t in texpack.load_textures(args.clean.read_bytes())}
    shots = []
    jobs = [(i, lambda im, ko=ko: set_vertical(im, ko, args.font), ja)
            for i, (ja, ko, _) in VERTICAL.items()]
    jobs.append((263, lambda im: set_card(im, args.font), "株式会社"))

    for index, build, ja in jobs:
        tex = current[index]
        before = texpack.decode(tex).convert("RGBA")
        canvas = build(before)
        blob = texenc.encode_indices(tex, texenc.quantise(canvas, tex.palette))
        if len(blob) != len(tex.image):
            raise SystemExit(f"tex{index}: size changed")
        record = tex.index * 2 + 2
        offset = int.from_bytes(data[record * 4:record * 4 + 4], "little")
        data[offset:offset + len(blob)] = blob
        shots.append((before, canvas))
        print(f"   tex{index:04d}  {ja} set")

    args.out.write_bytes(bytes(data))
    pad = 6
    w = max(b.width for b, _ in shots)
    h = max(b.height for b, _ in shots)
    sheet = Image.new("RGB", ((w + pad) * 2 + pad, (h + pad) * len(shots) + pad), (30, 30, 44))
    for n, (before, after) in enumerate(shots):
        for k, im in enumerate((before, after)):
            bg = Image.new("RGBA", im.size, (30, 30, 44, 255))
            sheet.paste(Image.alpha_composite(bg, im).convert("RGB"),
                        (pad + k * (w + pad), pad + n * (h + pad)))
    sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST).save(args.preview)
    print(f"-> {args.out}\n-> {args.preview}")


if __name__ == "__main__":
    main()

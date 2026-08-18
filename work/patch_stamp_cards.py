"""The two 0000 textures no generic pass could handle: the 黙秘 card and the 証明済 stamp.

The card is vertical type -- two characters stacked -- and the stamp is set on a tilt with
one word on an arc, so neither fits the label patcher's horizontal-box model.  Both are
rebuilt here from what is actually in the texture: the card keeps its gold and its border and
only the two characters change; the stamp keeps its worn ring, the inside is wiped to the
radius where the ring starts, and the Korean is drawn at the same tilt, the title word laid
character by character along the same arc.

証明済 is three characters and so is 증명됨, which keeps the big word the same weight in the
same space.  The arc word is the game's own title, 원격수사.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import texenc
import texpack

ROOT = Path(r"D:\psp\원격수사")
SERIF = Path(r"C:\Windows\Fonts\HANBatangB.ttf")


def card_mokuhi(tex, font_path: Path) -> Image.Image:
    """묵/비 stacked on the gold card, in the card's own black."""
    image = texpack.decode(tex).convert("RGBA")
    px = np.asarray(image).astype(np.int32)
    solid = px[:, :, 3] > 128
    luma = px[:, :, :3].mean(axis=2)
    ink = solid & (luma < 90)
    gold = solid & ~ink
    back = tuple(int(v) for v in np.median(px[gold], axis=0))
    ys, xs = np.nonzero(ink)
    box = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))

    out = image.copy()
    draw = ImageDraw.Draw(out)
    draw.rectangle(box, fill=back)
    height = box[3] - box[1] + 1
    per = height // 2 - 2
    font = ImageFont.truetype(str(font_path), per)
    cx = (box[0] + box[2]) / 2
    y = box[1] - 2
    ink = (20, 16, 10, 255)
    for ch in "묵비":
        b = draw.textbbox((0, 0), ch, font=font)
        x0 = cx - (b[2] - b[0]) / 2 - b[0]
        # the original is a heavy brush face; batang needs thickening to sit beside it
        for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1), (2, 0), (0, 2)):
            draw.text((x0 + dx, y - b[1] + dy), ch, font=font, fill=ink)
        y += per + 10
    return out


def stamp_proven(tex, font_path: Path) -> Image.Image:
    """The stamp, re-set in Korean at its own tilt."""
    image = texpack.decode(tex).convert("RGBA")
    px = np.asarray(image).astype(np.int32)
    solid = px[:, :, 3] > 128
    colour = tuple(int(v) for v in np.median(px[solid], axis=0)[:3]) + (255,)

    ys, xs = np.nonzero(solid)
    cy, cx = float(ys.mean()), float(xs.mean())
    r = np.sqrt((ys - cy) ** 2 + (xs - cx) ** 2)
    outer = float(np.percentile(r, 99))
    ring_inner = outer - 14          # the ring band plus its worn edge

    # Wipe everything inside the ring -- and also the two tilted bands where the big word and
    # the bottom word cross the ring itself.  証明済 runs edge to edge, over the ring, so a
    # radius test alone leaves its first and last strokes standing on the band.
    tilt = 20.0                       # the original rises to the right at about this angle
    yy, xx = np.mgrid[0:image.height, 0:image.width]
    dist = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    ca, sa = math.cos(math.radians(tilt)), math.sin(math.radians(tilt))
    ry = -(xx - cx) * sa + (yy - cy) * ca      # vertical position in the tilted frame
    big_band = np.abs(ry + 4) < 24
    low_band = np.abs(ry - 32) < 9
    keep = solid & (dist >= ring_inner) & ~big_band & ~low_band
    base = np.zeros_like(px, dtype=np.uint8)
    base[keep] = px[keep].astype(np.uint8)
    layer = Image.new("RGBA", (image.width * 2, image.height * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    lcx, lcy = image.width, image.height

    # the big word spans edge to edge like the original, crossing the ring on both sides
    big = ImageFont.truetype(str(font_path), 40)
    word = Image.new("RGBA", (200, 60), (0, 0, 0, 0))
    wd = ImageDraw.Draw(word)
    b = wd.textbbox((0, 0), "증명됨", font=big)
    for dx in (0, 1):
        wd.text((2 - b[0] + dx, 2 - b[1]), "증명됨", font=big, fill=colour)
    word = word.crop((0, 0, b[2] - b[0] + 5, b[3] - b[1] + 5))
    word = word.resize((126, word.height), Image.LANCZOS)
    layer.alpha_composite(word, (int(lcx - 63), int(lcy - word.height / 2 - 4)))
    small = ImageFont.truetype(str(font_path), 13)
    b = draw.textbbox((0, 0), "증명되었습니다", font=small)
    draw.text((lcx - (b[2] - b[0]) / 2 - b[0], lcy + 22 - b[1]),
              "증명되었습니다", font=small, fill=colour)

    # the title, character by character along the top arc
    arc = ImageFont.truetype(str(font_path), 15)
    radius = ring_inner - 9
    word = "원격수사"
    spread = 52.0
    for i, ch in enumerate(word):
        theta = math.radians(-90 - spread / 2 + spread * i / (len(word) - 1))
        gx = lcx + radius * math.cos(theta)
        gy = lcy + radius * math.sin(theta)
        glyph = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glyph)
        gb = gd.textbbox((0, 0), ch, font=arc)
        gd.text((12 - (gb[2] - gb[0]) / 2 - gb[0], 12 - (gb[3] - gb[1]) / 2 - gb[1]),
                ch, font=arc, fill=colour)
        glyph = glyph.rotate(-(math.degrees(theta) + 90), resample=Image.BICUBIC,
                             expand=False)
        layer.alpha_composite(glyph, (int(gx) - 12, int(gy) - 12))

    layer = layer.rotate(tilt, resample=Image.BICUBIC, center=(lcx, lcy))
    layer = layer.crop((lcx - cx, lcy - cy, lcx - cx + image.width, lcy - cy + image.height))

    out = Image.fromarray(base, "RGBA")
    out.alpha_composite(layer)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--clean", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--font", type=Path, default=SERIF)
    parser.add_argument("--preview", type=Path, default=ROOT / "build" / "stamp_cards.png")
    args = parser.parse_args()

    data = bytearray(args.stream.read_bytes())
    textures = {t.index: t for t in texpack.load_textures(args.clean.read_bytes())}
    jobs = {54: card_mokuhi, 277: stamp_proven}
    shots = []
    for index, build in jobs.items():
        tex = textures[index]
        canvas = build(tex, args.font)
        blob = texenc.encode_indices(tex, texenc.quantise(canvas, tex.palette))
        if len(blob) != len(tex.image):
            raise SystemExit(f"tex{index}: size changed")
        record = tex.index * 2 + 2
        offset = int.from_bytes(data[record * 4:record * 4 + 4], "little")
        data[offset:offset + len(blob)] = blob
        shots.append((texpack.decode(tex).convert("RGBA"), canvas))
        print(f"   tex{index:04d} set")

    args.out.write_bytes(bytes(data))
    pad, sc = 6, 2
    w, h = 128 * sc, 128 * sc
    sheet = Image.new("RGB", ((w + pad) * 2 + pad, (h + pad) * len(shots) + pad), (40, 40, 56))
    for n, (before, after) in enumerate(shots):
        for k, im in enumerate((before, after)):
            bg = Image.new("RGBA", im.size, (40, 40, 56, 255))
            f = Image.alpha_composite(bg, im).convert("RGB").resize((w, h), Image.NEAREST)
            sheet.paste(f, (pad + k * (w + pad), pad + n * (h + pad)))
    sheet.save(args.preview)
    print(f"-> {args.out}\n-> {args.preview}")


if __name__ == "__main__":
    main()

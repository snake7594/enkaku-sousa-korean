"""Replace the remaining Japanese labels: chapter cards, はい/いいえ, 戻る and the rest.

These were missed because nothing pointed at them.  Comparing the patched texture stream
against the original shows which of the 449 have never been written to, and 22 of them turned
out to be the chapter title cards the game shows between scenes -- 事件の発端, 不測の再会 and
so on -- which is about as visible as a texture gets.

They are white type on a transparent background, not type on a panel, so the box has to be
cleared to transparent rather than filled with a colour, and the ink colour has to come from
the pixels that are actually opaque.  Filling with the median of the whole box, which works on
the newspaper, would paint a grey rectangle over the scene here.
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
GOTHIC = Path(r"C:\Windows\Fonts\malgunbd.ttf")


def ink_colour(px: np.ndarray, box):
    """The colour of the letter body, and of its outline if it has one.

    Taking the median of every opaque pixel works on flat type and fails on outlined type:
    the relationship badges are white inside a heavy black edge, and the median landed on the
    edge, so the Korean came out almost invisible against the scene.  Eroding the opaque mask
    by a pixel removes the edge and leaves the body, and what erosion removed is the edge.
    """
    x0, y0, x1, y1 = box
    patch = px[y0:y1 + 1, x0:x1 + 1]
    solid = patch[:, :, 3] > 170
    if not solid.any():
        return (255, 255, 255, 255), None
    luma = patch[:, :, :3].mean(axis=2)
    lo, hi = np.percentile(luma[solid], 5), np.percentile(luma[solid], 95)
    if hi - lo < 90:                       # one flat colour, like the chapter cards
        return tuple(int(v) for v in np.median(patch[solid], axis=0)[:3]) + (255,), None

    # Two colours, and the median falls between them: 66 on a badge whose outline is 2 and
    # whose body is 250.  Split at the midpoint, then let erosion say which side is the body,
    # since the outline is the part a one-pixel erosion removes.
    mid = (lo + hi) / 2
    light, dark = solid & (luma >= mid), solid & (luma < mid)
    inner = solid.copy()
    for axis in (0, 1):
        for step in (1, -1):
            inner &= np.roll(solid, step, axis=axis)
    body = light if (inner & light).sum() >= (inner & dark).sum() else dark
    other = dark if body is light else light
    core = tuple(int(v) for v in np.median(patch[body], axis=0)[:3]) + (255,)
    edge = (tuple(int(v) for v in np.median(patch[other], axis=0)[:3]) + (255,)
            if other.sum() >= 8 else None)
    return core, edge


def draw_text(draw, xy, text, font, core, edge):
    if edge:
        x, y = xy
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    draw.text((x + dx, y + dy), text, font=font, fill=edge)
    draw.text(xy, text, font=font, fill=core)


def fit(draw, text, font_path, box, max_size):
    x0, y0, x1, y1 = box
    width, height = x1 - x0 + 1, y1 - y0 + 1
    size = max_size
    while size > 6:
        font = ImageFont.truetype(str(font_path), size)
        b = draw.textbbox((0, 0), text, font=font)
        if (b[2] - b[0]) <= width and (b[3] - b[1]) <= height:
            return font, b
        size -= 1
    font = ImageFont.truetype(str(font_path), 7)
    return font, draw.textbbox((0, 0), text, font=font)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "work" / "labels.json")
    parser.add_argument("--clean", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0_ko7.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "stream0_ko8.bin")
    parser.add_argument("--preview", type=Path, default=ROOT / "build" / "labels_ko.png")
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "labels_report.json")
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    data = bytearray(args.stream.read_bytes())
    textures = {t.index: t for t in texpack.load_textures(args.clean.read_bytes())}
    shots, done = [], []

    for entry in config["textures"]:
        tex = textures.get(entry["index"])
        if tex is None:
            continue
        original = texpack.decode(tex).convert("RGBA")
        px = np.asarray(original).astype(np.int32)
        canvas = original.copy()
        draw = ImageDraw.Draw(canvas)
        font_path = GOTHIC if entry.get("font") == "gothic" else SERIF
        palette = np.frombuffer(tex.palette, dtype=np.uint8)
        palette = palette[: (len(palette) // 4) * 4].reshape(-1, 4)
        transparent = palette[palette[:, 3] == 0]
        clear = tuple(int(v) for v in transparent[0]) if len(transparent) else (0, 0, 0, 0)
        sizes = []

        for label in entry["labels"]:
            box = tuple(label["box"])
            ink, edge = ink_colour(px, box)
            # Clearing to (0,0,0,0) is not the same as clearing to nothing.  The quantiser
            # weights alpha four times, and 예/아니요 came out on a grey slab because this
            # palette's clear entry carries a grey RGB while another entry is near-black at
            # alpha 22 -- from pure black the near-black entry is the closer match.  Writing
            # the palette's own clear colour removes the choice.
            draw.rectangle(box, fill=clear)
            x0, y0, x1, y1 = box
            width, height = x1 - x0 + 1, y1 - y0 + 1
            if label.get("vertical"):
                # The relationship badges are set one character above the next in a 32x64
                # box, so they need the column treatment rather than a fitted line.
                text = label["ko"]
                weights = [0.34 if not c.strip() else 1.0 for c in text]
                unit = height / sum(weights)
                size = max(7, int(min(width, unit) + 1))
                while size > 6:
                    font = ImageFont.truetype(str(font_path), size)
                    widest = max((draw.textbbox((0, 0), c, font=font)[2]
                                  for c in text if c.strip()), default=0)
                    if widest <= width:
                        break
                    size -= 1
                font = ImageFont.truetype(str(font_path), size)
                at = 0.0
                for ch, weight in zip(text, weights):
                    if ch.strip():
                        b = draw.textbbox((0, 0), ch, font=font)
                        draw_text(draw,
                                  (x0 + (width - (b[2] - b[0])) / 2 - b[0],
                                   y0 + at * unit + (weight * unit - (b[3] - b[1])) / 2 - b[1]),
                                  ch, font, ink, edge)
                    at += weight
                sizes.append(size)
                continue
            font, b = fit(draw, label["ko"], font_path, box,
                          entry.get("max_size", box[3] - box[1] + 1))
            if label.get("align") == "left":
                x = x0 - b[0]
            else:
                x = x0 + (width - (b[2] - b[0])) / 2 - b[0]
            y = y0 + (height - (b[3] - b[1])) / 2 - b[1]
            draw_text(draw, (x, y), label["ko"], font, ink, edge)
            sizes.append(font.size)

        indices = texenc.quantise(canvas, tex.palette)
        blob = texenc.encode_indices(tex, indices)
        record = tex.index * 2 + 2
        offset = int.from_bytes(data[record * 4:record * 4 + 4], "little")
        if len(blob) != len(tex.image):
            print(f"   tex{tex.index:04d}: size changed, skipped")
            continue
        data[offset:offset + len(blob)] = blob
        done.append({"index": tex.index, "labels": len(entry["labels"]), "sizes_px": sizes})
        shots.append((tex.index, original, canvas))
        first = entry["labels"][0]
        print(f"   tex{tex.index:04d}  {first['ja']} -> {first['ko']}"
              f"{'' if len(entry['labels']) == 1 else f'  (+{len(entry[chr(108)+chr(97)+chr(98)+chr(101)+chr(108)+chr(115)]) - 1} more)'}"
              f"  {sizes}px")

    args.out.write_bytes(bytes(data))
    args.report.write_text(json.dumps({"schema": "enkaku_labels_v1", "patched": done},
                                      ensure_ascii=False, indent=1), encoding="utf-8")

    if shots:
        scale = 2
        width = max(o.width for _, o, _ in shots) * scale + 60
        height = sum(o.height * scale * 2 + 10 for _, o, _ in shots) + 8
        sheet = Image.new("RGBA", (width, height), (18, 18, 28, 255))
        label_font = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 12)
        d = ImageDraw.Draw(sheet)
        y = 4
        for index, before, after in shots:
            for image in (before, after):
                sheet.alpha_composite(
                    image.resize((image.width * scale, image.height * scale), Image.NEAREST),
                    (56, y))
                y += image.height * scale + 2
            d.text((4, y - image.height * scale * 2), f"{index:04d}",
                   font=label_font, fill=(255, 200, 80, 255))
            y += 6
        sheet.convert("RGB").save(args.preview)
    print(f"\n{len(done)} textures -> {args.out}\n-> {args.preview}")


if __name__ == "__main__":
    main()

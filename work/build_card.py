"""Redraw the business card in Korean, keeping the card itself.

Unlike the menu strips this texture is a picture, not a label: it has a border, a paper
tone and a drop shadow, and redrawing the whole 128x256 from scratch would lose all of
that.  So the original is kept and only the columns of Japanese are painted over, using a
paper colour sampled from the card itself.

The text is vertical, which the layout depends on -- the company sits to the right, the
name runs down the middle at a larger size, the address is a thin column on the left -- so
Korean is set the same way, one syllable under the next.
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

# (x centre, y top, size, text) in texture pixels, right to left as the card reads
COLUMNS = [
    (96, 20, 9, "주식회사 시라카와 하우징"),
    (79, 30, 8, "대표이사"),
    (57, 34, 15, "시라카와 이치로"),
    (33, 26, 6, "도쿄도 미나토구"),
    (25, 26, 6, "아카사카 1-2-3"),
    (17, 26, 6, "TEL 03-1234-5678"),
]
# region of the card that holds text, cleared before drawing
CLEAR = (12, 16, 104, 236)


def draw_column(canvas: Image.Image, x: int, y: int, px: int, text: str,
                font_path: Path, colour: tuple[int, int, int, int]) -> None:
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(str(font_path), px)
    for char in text:
        if char == " ":
            y += px // 2
            continue
        box = draw.textbbox((0, 0), char, font=font)
        draw.text((x - (box[2] - box[0]) / 2 - box[0], y - box[1]), char,
                  font=font, fill=colour)
        y += px + 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=int, default=263)
    parser.add_argument("--font", type=Path, default=SERIF)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0_ko.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "stream0_ko.bin")
    parser.add_argument("--preview", type=Path, default=ROOT / "build" / "card_ko.png")
    args = parser.parse_args()

    data = bytearray(args.stream.read_bytes())
    tex = next(t for t in texpack.load_textures(bytes(data)) if t.index == args.index)
    original = texpack.decode(tex).convert("RGBA")
    print(f"tex{tex.index:04d}  {tex.width}x{tex.height}")

    # paper tone and ink colour, taken from the card rather than guessed
    pixels = np.asarray(original)
    patch = pixels[CLEAR[1]:CLEAR[3], CLEAR[0]:CLEAR[2]].reshape(-1, 4)
    opaque = patch[patch[:, 3] > 200]
    paper = tuple(int(v) for v in np.median(opaque, axis=0)) if len(opaque) else (235, 232, 222, 255)
    ink = tuple(int(v) for v in opaque[opaque[:, :3].sum(axis=1).argmin()]) if len(opaque) else (20, 20, 20, 255)
    print(f"   paper {paper}, ink {ink}")

    card = original.copy()
    ImageDraw.Draw(card).rectangle(CLEAR, fill=paper)
    for x, y, px, text in COLUMNS:
        draw_column(card, x, y, px, text, args.font, ink)

    indices = texenc.quantise(card, tex.palette)
    blob = texenc.encode_indices(tex, indices)
    record = tex.index * 2 + 2
    offset = int.from_bytes(data[record * 4:record * 4 + 4], "little")
    if len(blob) != len(tex.image) or \
            bytes(data[offset:offset + len(blob)]) != tex.image[:len(blob)]:
        print("   record check failed, nothing written")
        return
    data[offset:offset + len(blob)] = blob
    args.out.write_bytes(bytes(data))

    colours = np.frombuffer(tex.palette, dtype=np.uint8)
    colours = colours[: (len(colours) // 4) * 4].reshape(-1, 4)
    shown = Image.fromarray(colours[indices], "RGBA")
    side = Image.new("RGBA", (tex.width * 2 + 12, tex.height + 8), (24, 24, 24, 255))
    side.paste(original, (4, 4), original)
    side.paste(shown, (tex.width + 8, 4), shown)
    side.resize((side.width * 2, side.height * 2), Image.NEAREST).save(args.preview)
    print(f"-> {args.out}\n-> {args.preview}")


if __name__ == "__main__":
    main()

"""Make a labelled visual comparison between game glyphs and system-font candidates."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import font as fontlib


ROOT = Path(__file__).resolve().parents[1]
STREAM = ROOT / "font_extract" / "script_stream.bin"
FONT_OFFSET = 0x80
FONT_TILES = 684
SYSTEM_FONT = Path(r"C:\Windows\Fonts\BIZ-UDGothicB.ttc")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("target", type=int)
    p.add_argument("candidates", nargs="+")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--scale", type=int, default=10)
    args = p.parse_args()

    glyphs = fontlib.tiles_to_glyphs(STREAM.read_bytes(), FONT_OFFSET, FONT_TILES)
    scale = args.scale
    label_font = ImageFont.truetype(str(SYSTEM_FONT), 24)
    target = Image.fromarray((glyphs[args.target] * 17).astype(np.uint8), "L").resize((16 * scale, 16 * scale), Image.Resampling.NEAREST)

    cards: list[Image.Image] = []
    for candidate in args.candidates:
        rendered = Image.new("L", (16, 16), 0)
        draw = ImageDraw.Draw(rendered)
        # Center a Japanese glyph in a 16x16 box using a large font.
        draw.text((0, -5), candidate, font=ImageFont.truetype(str(SYSTEM_FONT), 18), fill=255, stroke_width=0)
        rendered = rendered.resize((16 * scale, 16 * scale), Image.Resampling.NEAREST)
        card = Image.new("RGB", (16 * scale, 22 * scale), "white")
        card.paste(Image.merge("RGB", (rendered, rendered, rendered)), (0, 0))
        ImageDraw.Draw(card).text((2, 16 * scale), candidate, font=label_font, fill="black")
        cards.append(card)

    width = max(target.width, len(cards) * 16 * scale)
    height = target.height + 22 * scale + 45
    canvas = Image.new("RGB", (width, height), "white")
    canvas.paste(Image.merge("RGB", (target, target, target)), (0, 0))
    d = ImageDraw.Draw(canvas)
    d.text((2, target.height + 2), f"GAME [{args.target}]", font=label_font, fill="red")
    y = target.height + 45
    for i, card in enumerate(cards):
        canvas.paste(card, (i * 16 * scale, y))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.out)
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

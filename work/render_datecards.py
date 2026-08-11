"""Render the Korean date cards and show them beside the originals.

The date cards are the most regular set in the game -- 11月11日 through 12月2日, plus nine
"起訴まで あと N日" counters -- so they are worth doing programmatically rather than by hand.
This renders one first and puts it next to the original, because matching the existing look
(weight, size, vertical position, the slight gradient on the strokes) is a judgement that has
to be made by eye before committing to twenty-two of them.

The palette is the texture's own; nothing about the record's size or layout changes, so the
result drops straight back into the stream.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import texenc
import texpack

ROOT = Path(r"D:\psp\원격수사")
FONT = Path(r"D:\psp\타임트레블러즈\SeoulHangangB.ttf")


def render(text: str, size: tuple[int, int], px: int, dy: int,
           font_path: Path = FONT, tracking: float = 0.0) -> Image.Image:
    """White text on transparent, centred, at 4x then downsampled for smooth edges.

    Characters are placed one at a time so the gap between them can be widened: the
    original cards space `11 月 11 日` well apart, and a single draw call cannot reproduce
    that.  Tracking is given as a fraction of the point size so it scales with px.
    """
    scale = 4
    big = Image.new("RGBA", (size[0] * scale, size[1] * scale), (255, 255, 255, 0))
    draw = ImageDraw.Draw(big)
    font = ImageFont.truetype(str(font_path), px * scale)
    gap = tracking * px * scale

    widths = [draw.textlength(c, font=font) for c in text]
    total = sum(widths) + gap * (len(text) - 1)
    box = draw.textbbox((0, 0), text, font=font)
    x = (big.width - total) / 2
    y = (big.height - (box[3] - box[1])) / 2 - box[1] + dy * scale
    for char, width in zip(text, widths):
        draw.text((x, y), char, font=font, fill=(255, 255, 255, 255))
        x += width + gap
    return big.resize(size, Image.LANCZOS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=int, default=23)
    parser.add_argument("--text", default="11월 11일")
    parser.add_argument("--px", type=int, default=20)
    parser.add_argument("--dy", type=int, default=0)
    parser.add_argument("--font", type=Path, default=FONT)
    parser.add_argument("--tracking", type=float, default=0.0,
                        help="extra gap between characters, as a fraction of the size")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "datecard_preview.png")
    args = parser.parse_args()

    data = (ROOT / "build" / "stream0.bin").read_bytes()
    tex = next(t for t in texpack.load_textures(data) if t.index == args.index)
    original = texpack.decode(tex)
    print(f"tex{tex.index:04d}  {tex.width}x{tex.height}  psm{tex.psm}")

    drawn = render(args.text, (tex.width, tex.height), args.px, args.dy, args.font, args.tracking)
    indices = texenc.quantise(drawn, tex.palette)
    rebuilt = texenc.encode_indices(tex, indices)
    print(f"   encoded {len(rebuilt)} bytes "
          f"(original image is {len(tex.image)})")

    # show what the game would actually display: the quantised result, not the raw render
    colours = np.frombuffer(tex.palette, dtype=np.uint8)
    colours = colours[: (len(colours) // 4) * 4].reshape(-1, 4)
    shown = Image.fromarray(colours[indices], "RGBA")

    pad = 6
    canvas = Image.new("RGBA", (tex.width + pad * 2,
                                tex.height * 3 + pad * 4), (24, 24, 24, 255))
    for n, layer in enumerate((original, drawn, shown)):
        canvas.paste(layer, (pad, pad + n * (tex.height + pad)), layer)
    canvas.resize((canvas.width * 2, canvas.height * 2), Image.NEAREST).save(args.out)
    print(f"   top original / middle rendered / bottom after palette mapping")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

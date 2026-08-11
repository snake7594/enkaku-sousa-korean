"""Generate all the Korean date cards and write them back into stream 0.

Tracking is applied between words rather than between every character: the original spaces
`11 月 11 日` apart, but `11월 11일` wants its digits touching and only the gap after each
word widened.  Applying it uniformly, as the first pass did, pushed the numerals apart and
read as `1 1월  1 1일`.

The 256x32 group runs in calendar order from index 23, so the mapping is positional rather
than guessed; a contact sheet of the result is written so the whole set can be checked at
once before it goes into the stream.
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

# calendar order, matching the sheet: 11/11-11/30, 12/1, 12/2
DATES = [f"11월 {d}일" for d in range(11, 31)] + ["12월 1일", "12월 2일"]
COUNTERS = [f"기소까지 {n}일" for n in range(1, 10)]


def render(text: str, size: tuple[int, int], px: int, dy: int,
           font_path: Path, tracking: float) -> Image.Image:
    """Words are laid out with extra space between them; letters keep their own spacing."""
    scale = 4
    big = Image.new("RGBA", (size[0] * scale, size[1] * scale), (255, 255, 255, 0))
    draw = ImageDraw.Draw(big)
    font = ImageFont.truetype(str(font_path), px * scale)
    gap = tracking * px * scale

    words = text.split(" ")
    widths = [draw.textlength(w, font=font) for w in words]
    total = sum(widths) + gap * (len(words) - 1)
    box = draw.textbbox((0, 0), text, font=font)
    x = (big.width - total) / 2
    y = (big.height - (box[3] - box[1])) / 2 - box[1] + dy * scale
    for word, width in zip(words, widths):
        draw.text((x, y), word, font=font, fill=(255, 255, 255, 255))
        x += width + gap
    return big.resize(size, Image.LANCZOS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--px", type=int, default=26)
    parser.add_argument("--dy", type=int, default=0)
    parser.add_argument("--tracking", type=float, default=0.5)
    parser.add_argument("--font", type=Path, default=SERIF)
    parser.add_argument("--start", type=int, default=23)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "stream0_ko.bin")
    parser.add_argument("--sheet", type=Path,
                        default=ROOT / "build" / "datecards_ko.png")
    args = parser.parse_args()

    data = bytearray(args.stream.read_bytes())
    textures = {t.index: t for t in texpack.load_textures(bytes(data))}
    labels = DATES + COUNTERS

    rendered, written = [], 0
    for n, text in enumerate(labels):
        index = args.start + n
        tex = textures.get(index)
        if tex is None or (tex.width, tex.height) != (256, 32):
            print(f"   tex{index:04d} is not a 256x32 card -- stopping")
            break
        drawn = render(text, (tex.width, tex.height), args.px, args.dy,
                       args.font, args.tracking)
        indices = texenc.quantise(drawn, tex.palette)
        blob = texenc.encode_indices(tex, indices)
        if len(blob) != len(tex.image):
            print(f"   tex{index:04d}: size changed, refusing")
            break
        # Texture keeps the bytes, not where they came from; the archive's record table does.
        # Image records sit at index*2 + 2, the same mapping texpack.record_index uses.
        record = tex.index * 2 + 2
        offset = int.from_bytes(data[record * 4:record * 4 + 4], "little")
        if bytes(data[offset:offset + len(blob)]) != tex.image[:len(blob)]:
            print(f"   tex{index:04d}: record {record} does not point at its image")
            break
        data[offset:offset + len(blob)] = blob
        colours = np.frombuffer(tex.palette, dtype=np.uint8)
        colours = colours[: (len(colours) // 4) * 4].reshape(-1, 4)
        rendered.append(Image.fromarray(colours[indices], "RGBA"))
        written += 1

    args.out.write_bytes(bytes(data))
    print(f"{written}/{len(labels)} cards written -> {args.out}")

    if rendered:
        pad, cols = 4, 4
        rows = (len(rendered) + cols - 1) // cols
        sheet = Image.new("RGBA", (cols * (256 + pad) + pad,
                                   rows * (32 + pad) + pad), (24, 24, 24, 255))
        for n, im in enumerate(rendered):
            r, c = divmod(n, cols)
            sheet.paste(im, (pad + c * (256 + pad), pad + r * (32 + pad)), im)
        sheet.save(args.sheet)
        print(f"-> {args.sheet}")


if __name__ == "__main__":
    main()

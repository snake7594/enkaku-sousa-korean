"""Lay the 512x32 question strings out one per row, at full size, so they can be read.

The all-in-one contact sheet shrank each 512-pixel strip into a thumbnail, and reading the
Japanese off it produced errors -- 乗車記録 came out as 車単記録, 拭き取る as 拭き消る.  Those
would have gone straight into the translation.  At full width the text is legible, so the
sheets are split into pages instead.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

import texpack

ROOT = Path(r"D:\psp\원격수사")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-page", type=int, default=16)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0.bin")
    args = parser.parse_args()

    data = args.stream.read_bytes()
    group = [t for t in texpack.load_textures(data) if (t.width, t.height) == (512, 32)]
    print(f"{len(group)} question strips, indices {group[0].index}-{group[-1].index}")

    pad = 2
    for page in range(0, len(group), args.per_page):
        chunk = group[page:page + args.per_page]
        images = [texpack.decode(t) for t in chunk]
        sheet = Image.new("RGBA", (512 + pad * 2, len(images) * (32 + pad) + pad),
                          (20, 20, 20, 255))
        for n, im in enumerate(images):
            sheet.paste(im, (pad, pad + n * (32 + pad)), im)
        out = ROOT / "build" / f"questions_p{page // args.per_page}.png"
        sheet.save(out)
        print(f"   {out.name}: indices {[t.index for t in chunk]}")


if __name__ == "__main__":
    main()

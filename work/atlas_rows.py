"""Split the HUD atlas into its four rows by fixed pitch, then into words by column gaps.

Row detection by blank scanlines fails here: the four rows touch, so the whole 64 pixels
read as one band.  The rows are evenly spaced though -- 64 / 4 = 16 -- so the split can be
taken as given and only the horizontal boundaries need finding.

This prints the word boxes so they can be checked against the rendered atlas before anything
is written.  Getting a boundary wrong here paints over the neighbouring word, which is why
the atlas has been left alone until now.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

import texpack

ROOT = Path(r"D:\psp\원격수사")


def runs(mask: np.ndarray, gap: int, minimum: int) -> list[tuple[int, int]]:
    out, start, blank = [], None, 0
    for i, on in enumerate(mask):
        if on:
            if start is None:
                start = i
            blank = 0
        elif start is not None:
            blank += 1
            if blank >= gap:
                if i - blank - start + 1 >= minimum:
                    out.append((start, i - blank))
                start = None
    if start is not None and len(mask) - start >= minimum:
        out.append((start, len(mask) - 1))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=int, default=409)
    parser.add_argument("--rows", type=int, default=4)
    parser.add_argument("--gap", type=int, default=2)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "atlas_words.json")
    args = parser.parse_args()

    data = args.stream.read_bytes()
    tex = next(t for t in texpack.load_textures(data) if t.index == args.index)
    px = np.asarray(texpack.decode(tex).convert("RGBA")).astype(np.int32)
    # The atlas mixes two styles and a single threshold only catches one of them: the left
    # half is orange text on transparency, the right half white glyphs inside orange boxes.
    # Detecting alpha alone misses the boxed glyphs; detecting luminance alone misses the
    # orange text, because it *is* the median once most opaque pixels are orange.
    luma = px[:, :, :3].mean(axis=2)
    alpha = px[:, :, 3]
    opaque = alpha > 40
    boxed = opaque.mean(axis=0) > 0.9            # columns that are solid top to bottom
    floor = float(np.median(luma[opaque])) if opaque.any() else 0.0
    ink = np.where(boxed[None, :],
                   (np.abs(luma - floor) > 20) & opaque,   # inside a box: contrast
                   opaque)                                  # on transparency: any paint

    pitch = tex.height // args.rows
    print(f"tex{tex.index:04d} {tex.width}x{tex.height}, {args.rows} rows of {pitch}px")
    out = []
    for r in range(args.rows):
        top, bottom = r * pitch, (r + 1) * pitch - 1
        cols = ink[top:bottom + 1].sum(axis=0) >= 1
        words = runs(cols, args.gap, 6)
        print(f"   row {r} (y {top}-{bottom}): {len(words)} words")
        print(f"      {[(a, b - a + 1) for a, b in words]}")
        out.append({"row": r, "top": top, "bottom": bottom,
                    "words": [[a, b] for a, b in words]})

    args.out.write_text(json.dumps(out, indent=1), encoding="utf-8")

    # a magnified strip per row, so the boxes can be checked by eye
    image = texpack.decode(tex)
    strips = Image.new("RGBA", (tex.width * 4, args.rows * (pitch * 4 + 4)),
                       (20, 20, 20, 255))
    for r in range(args.rows):
        band = image.crop((0, r * pitch, tex.width, (r + 1) * pitch))
        strips.paste(band.resize((tex.width * 4, pitch * 4), Image.NEAREST),
                     (0, r * (pitch * 4 + 4)))
    strips.save(ROOT / "build" / f"atlas_{args.index}_rows.png")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

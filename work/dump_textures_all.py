"""Dump every texture in stream 0 to PNG, and build contact sheets to read them by.

The previous attempt guessed at the record header and produced three 257x257 images out of
449 -- the format was already parsed correctly in texpack, and re-deriving it was the
mistake.  This uses texpack.load_textures and texpack.decode, the same path
survey_textures.py uses to count 449.

Textures are grouped by size on the sheets because a run of identically-sized images is
almost always one set, and the Japanese ones -- date cards, menu labels -- are obvious at a
glance once they sit side by side.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from PIL import Image

import texpack

ROOT = Path(r"D:\psp\원격수사")


def sheet(images: list[Image.Image], cols: int, pad: int = 2) -> Image.Image:
    w = max(i.width for i in images)
    h = max(i.height for i in images)
    rows = (len(images) + cols - 1) // cols
    out = Image.new("RGBA", (cols * (w + pad) + pad, rows * (h + pad) + pad),
                    (32, 32, 32, 255))
    for n, im in enumerate(images):
        r, c = divmod(n, cols)
        out.paste(im, (pad + c * (w + pad), pad + r * (h + pad)), im)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "textures")
    parser.add_argument("--cols", type=int, default=8)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    data = args.stream.read_bytes()
    textures = texpack.load_textures(data)
    print(f"{len(textures)} textures in {args.stream.name}")

    by_size, meta, failed = defaultdict(list), [], 0
    for tex in textures:
        image = texpack.decode(tex)
        if image is None:
            failed += 1
            continue
        name = f"tex{tex.index:04d}_{image.width}x{image.height}.png"
        image.save(args.out / name)
        by_size[(image.width, image.height)].append((tex.index, image))
        meta.append({"index": tex.index, "record": tex.record_index,
                     "w": image.width, "h": image.height, "psm": tex.psm_name})

    print(f"   {len(meta)} written, {failed} could not be decoded")
    (args.out / "index.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")

    sheets = args.out / "sheets"
    sheets.mkdir(exist_ok=True)
    for (w, h), group in sorted(by_size.items(), key=lambda kv: -len(kv[1])):
        print(f"   {w:4d}x{h:<4d} {len(group):4d}  first indices {[i for i, _ in group[:6]]}")
        for page in range(0, len(group), args.cols * 12):
            chunk = group[page:page + args.cols * 12]
            sheet([im for _, im in chunk], args.cols).save(
                sheets / f"sheet_{w}x{h}_{page // (args.cols * 12)}.png")
    print(f"-> {args.out}\n-> {sheets}")


if __name__ == "__main__":
    main()

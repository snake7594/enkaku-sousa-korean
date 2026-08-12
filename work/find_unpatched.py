"""Show the textures that are still exactly as they shipped, so untouched Japanese stands out.

Issue #3 shows a save screen with セーブ and 削除 still in Japanese.  The bottom bar in that
same screenshot -- 選択, 戻る, 決定 -- was patched in v2.1, and the screenshot predates that
release, so those are already done.  The two menu items are the question.

Comparing the patched stream against the original says exactly which of the 449 textures have
never been written to.  Anything Japanese in the game either lives in one of those or is not a
texture at all, and that is worth knowing before hunting through the executable again.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import texpack

ROOT = Path(r"D:\psp\원격수사")
LABEL = Path(r"C:\Windows\Fonts\consola.ttf")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--patched", type=Path, default=ROOT / "build" / "stream0_ko7.bin")
    parser.add_argument("--max-width", type=int, default=256)
    parser.add_argument("--max-height", type=int, default=64)
    parser.add_argument("--page", type=int, default=0)
    parser.add_argument("--per-page", type=int, default=40)
    parser.add_argument("--scale", type=int, default=2)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "unpatched.json")
    args = parser.parse_args()

    clean = args.clean.read_bytes()
    patched = args.patched.read_bytes()
    textures = list(texpack.load_textures(clean))

    untouched = []
    for tex in textures:
        record = tex.index * 2 + 2
        offset = int.from_bytes(clean[record * 4:record * 4 + 4], "little")
        n = len(tex.image)
        if clean[offset:offset + n] == patched[offset:offset + n]:
            untouched.append(tex)

    small = [t for t in untouched
             if t.width <= args.max_width and t.height <= args.max_height]
    args.report.write_text(json.dumps(
        {"schema": "enkaku_unpatched_v1", "textures": len(textures),
         "untouched": len(untouched),
         "small_untouched": [{"index": t.index, "size": [t.width, t.height]} for t in small]},
        ensure_ascii=False, indent=1), encoding="utf-8")

    chunk = small[args.page * args.per_page:(args.page + 1) * args.per_page]
    pages = (len(small) + args.per_page - 1) // args.per_page
    out = args.out or ROOT / "build" / f"unpatched_p{args.page}.png"

    if chunk:
        width = max(t.width for t in chunk) * args.scale + 60
        height = sum(t.height * args.scale + 6 for t in chunk) + 6
        sheet = Image.new("RGB", (width, height), (24, 24, 24))
        draw = ImageDraw.Draw(sheet)
        font = ImageFont.truetype(str(LABEL), 12)
        y = 4
        for tex in chunk:
            image = texpack.decode(tex)
            if image is not None:
                # These are drawn over the scene, so most of each one is transparent.  Pasting
                # as RGB threw the alpha away and every chapter card came out a white slab.
                rgba = image.convert("RGBA").resize(
                    (tex.width * args.scale, tex.height * args.scale), Image.NEAREST)
                back = Image.new("RGBA", rgba.size, (18, 18, 28, 255))
                sheet.paste(Image.alpha_composite(back, rgba).convert("RGB"), (56, y))
            draw.text((4, y + 2), f"{tex.index:04d}", font=font, fill=(255, 200, 80))
            draw.text((4, y + 16), f"{tex.width}x{tex.height}", font=font, fill=(120, 120, 120))
            y += tex.height * args.scale + 6
        sheet.save(out)

    print(f"{len(textures)} textures, {len(untouched)} never written to, "
          f"{len(small)} of those are small enough to hold a label")
    print(f"page {args.page + 1} of {pages} -> {out}")


if __name__ == "__main__":
    main()

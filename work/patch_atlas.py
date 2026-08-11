"""Patch the HUD atlas words whose boundaries are unambiguous, and only those.

Column detection separates the atlas into runs, but only some of them are single words: in
rows where the glyphs touch, 次へ辞典Ｒ comes back as one 78-pixel run.  Painting Korean into
a run like that would erase its neighbours, and the HUD is the most-seen surface in the game.

So each entry below names the exact span it was measured at, and anything merged is left in
Japanese.  A span is only listed when the runs either side of it are separated by real gaps.

Korean is set to fit the span it replaces -- these slots are addressed by fixed UV
coordinates in the executable, so a word may not grow past the box it came from.
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
GOTHIC = Path(r"C:\Windows\Fonts\malgunbd.ttf")

# (row, x_start, x_end, japanese, korean) -- spans measured by work/atlas_rows.py
WORDS = [
    (0, 64, 125, "メニュー", "메뉴"),
    (1, 2, 30, "詳細", "상세"),
    (1, 34, 61, "なし", "없음"),
]
PITCH = 16


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=int, default=409)
    parser.add_argument("--font", type=Path, default=GOTHIC)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0_ko3.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "stream0_ko4.bin")
    parser.add_argument("--clean", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--preview", type=Path, default=ROOT / "build" / "atlas_ko.png")
    args = parser.parse_args()

    data = bytearray(args.stream.read_bytes())
    clean = args.clean.read_bytes()
    tex = next(t for t in texpack.load_textures(clean) if t.index == args.index)
    original = texpack.decode(tex).convert("RGBA")
    px = np.asarray(original).astype(np.int32)
    canvas = original.copy()
    draw = ImageDraw.Draw(canvas)
    print(f"tex{tex.index:04d} {tex.width}x{tex.height}")

    for row, x0, x1, ja, ko in WORDS:
        top, bottom = row * PITCH, (row + 1) * PITCH - 1
        patch = px[top:bottom + 1, x0:x1 + 1]
        solid = patch[patch[:, :, 3] > 40]
        if not len(solid):
            print(f"   row {row} {x0}-{x1}: nothing there, skipped")
            continue
        # The median runs across antialiased edges and comes back semi-transparent, which
        # rendered the Korean washed out.  Take the colour of the most solid pixels instead.
        core = solid[solid[:, 3] > 230]
        ink = tuple(int(v) for v in np.median(core if len(core) else solid, axis=0))
        ink = ink[:3] + (255,)
        # transparent background: clear to fully transparent, not to a sampled colour
        draw.rectangle((x0, top, x1, bottom), fill=(0, 0, 0, 0))

        width = x1 - x0 + 1
        size = PITCH
        while size > 6:
            font = ImageFont.truetype(str(args.font), size)
            b = draw.textbbox((0, 0), ko, font=font)
            if (b[2] - b[0]) <= width and (b[3] - b[1]) <= PITCH:
                break
            size -= 1
        font = ImageFont.truetype(str(args.font), size)
        b = draw.textbbox((0, 0), ko, font=font)
        draw.text((x0 + (width - (b[2] - b[0])) / 2 - b[0],
                   top + (PITCH - (b[3] - b[1])) / 2 - b[1]),
                  ko, font=font, fill=ink)
        print(f"   row {row} x{x0}-{x1}  {ja} -> {ko}  ({size}px, ink {ink})")

    indices = texenc.quantise(canvas, tex.palette)
    blob = texenc.encode_indices(tex, indices)
    record = tex.index * 2 + 2
    offset = int.from_bytes(data[record * 4:record * 4 + 4], "little")
    if len(blob) != len(tex.image):
        print("   size changed, nothing written")
        return
    data[offset:offset + len(blob)] = blob
    args.out.write_bytes(bytes(data))

    strip = Image.new("RGBA", (tex.width * 4, tex.height * 8 + 8), (20, 20, 20, 255))
    strip.paste(original.resize((tex.width * 4, tex.height * 4), Image.NEAREST), (0, 0))
    strip.paste(canvas.resize((tex.width * 4, tex.height * 4), Image.NEAREST),
                (0, tex.height * 4 + 8))
    strip.save(args.preview)
    print(f"-> {args.out}\n-> {args.preview}")


if __name__ == "__main__":
    main()

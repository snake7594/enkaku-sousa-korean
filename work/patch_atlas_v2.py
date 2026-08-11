"""Patch the HUD atlas on its measured 16-pixel character grid.

Gap detection could only separate the words that happen not to touch, so 次へ辞典Ｒ came back
as one run and the atlas was left half-done.  Rendering the rows against a pixel ruler
settled it: every glyph occupies exactly 16 pixels starting at x=0, which the isolated words
confirm independently -- メニュー spans 64-127, four cells of 16.

So each entry below is a cell range on that grid, not an estimate.  The button glyphs
(Ⓡ Ⓛ ○ △ ✛) and the pointer art are simply not listed, so nothing writes over them.

Korean is fitted inside the cells it replaces: these slots are addressed by fixed UV
coordinates in the executable, so a word cannot grow past its box.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import texenc
import texpack

ROOT = Path(r"D:\psp\원격수사")
GOTHIC = Path(r"C:\Windows\Fonts\malgunbd.ttf")
CELL = 16
PITCH = 16

# (row, first cell, cell count, japanese, korean)
WORDS = [
    (0, 0, 2, "残り", "남은"),
    (0, 4, 4, "メニュー", "메뉴"),
    (0, 8, 2, "午前", "오전"),
    (0, 10, 2, "不在", "부재"),
    (1, 0, 2, "詳細", "상세"),
    (1, 2, 2, "なし", "없음"),
    (1, 4, 2, "移動", "이동"),
    (1, 6, 2, "戻る", "뒤로"),
    (1, 8, 2, "正午", "정오"),
    (2, 1, 5, "スクロール", "스크롤"),
    (2, 6, 2, "決定", "결정"),
    (2, 8, 2, "午後", "오후"),
    (3, 0, 2, "次へ", "다음"),
    (3, 2, 2, "辞典", "사전"),
    (3, 6, 2, "選択", "선택"),
    (3, 8, 2, "不在", "부재"),
    (3, 10, 3, "定休日", "정기휴일"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=int, default=409)
    parser.add_argument("--font", type=Path, default=GOTHIC)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0_ko4.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "stream0_ko5.bin")
    parser.add_argument("--clean", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--preview", type=Path, default=ROOT / "build" / "atlas_ko2.png")
    args = parser.parse_args()

    data = bytearray(args.stream.read_bytes())
    clean = args.clean.read_bytes()
    tex = next(t for t in texpack.load_textures(clean) if t.index == args.index)
    original = texpack.decode(tex).convert("RGBA")
    px = np.asarray(original).astype(np.int32)
    canvas = original.copy()
    draw = ImageDraw.Draw(canvas)
    print(f"tex{tex.index:04d} {tex.width}x{tex.height}, {CELL}px grid")

    for row, cell, span, ja, ko in WORDS:
        x0, x1 = cell * CELL, (cell + span) * CELL - 1
        top, bottom = row * PITCH, (row + 1) * PITCH - 1
        patch = px[top:bottom + 1, x0:x1 + 1]
        solid = patch[patch[:, :, 3] > 40]
        if not len(solid):
            print(f"   row {row} cells {cell}-{cell + span - 1}: empty, skipped")
            continue
        core = solid[solid[:, 3] > 230]
        ink = tuple(int(v) for v in np.median(core if len(core) else solid, axis=0))
        ink = ink[:3] + (255,)
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
                   top + (PITCH - (b[3] - b[1])) / 2 - b[1]), ko, font=font, fill=ink)
        print(f"   row {row} x{x0:3d}-{x1:3d}  {ja} -> {ko}  ({size}px)")

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

"""Align the Korean labels to where the Japanese ones were, in both layers.

The grey panel text and the yellow overlay drifted apart for two separate reasons, and both
are fixed by measuring the original rather than choosing coordinates:

  overlays  the Japanese ink starts at x=1 in its 128x32 box -- left aligned.  fit() centred
            the Korean, which pushed the selected row to the right of the grey one.
  panel     the eight Japanese rows sit at x=36, top y=75, pitch 22, height 17.  The Korean
            was drawn at x=30 from y=80 with a different pitch.

Each overlay keeps whatever alignment its own original had: a box whose ink starts at the
very edge is set flush left at that edge, anything else stays centred, so the value columns
(보통, 중간) are not disturbed while the item names line up.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import texenc
import texpack
from build_menu_v2 import LABELS

ROOT = Path(r"D:\psp\원격수사")
REGULAR = Path(r"C:\Windows\Fonts\HANBatang.ttf")

TITLE = "설정"
BLURB = ["플레이 환경을 설정할 수 있습니다.",
         "취향에 맞게 선택해 주십시오.",
         "끝내려면 「돌아가기」를 선택하십시오."]
ITEMS = ["문장 표시 속도", "음량  음악", "음량  효과음", "음량  음성",
         "미독 빨리감기", "데이터 설치", "초기 상태로", "돌아가기"]


def ink_box(px: np.ndarray, thresh: float = 14.0):
    luma = px[:, :, :3].mean(axis=2)
    floor = float(np.median(luma))
    mask = np.abs(luma - floor) > thresh
    if px.shape[2] == 4 and px[:, :, 3].min() < 250:
        mask &= px[:, :, 3] > 40
    if not mask.any():
        return None
    ys, xs = np.nonzero(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def colours_of(px: np.ndarray, box):
    """Ink and field colour, split by luminance so the fill actually covers the glyphs."""
    luma = px[:, :, :3].mean(axis=2)
    floor = float(np.median(luma))
    mask = np.abs(luma - floor) > 14
    if px.shape[2] == 4 and px[:, :, 3].min() < 250:
        mask &= px[:, :, 3] > 40
    back = tuple(int(v) for v in np.median(px[~mask], axis=0)) if (~mask).any() \
        else (0, 0, 0, 0)
    ink = tuple(int(v) for v in np.median(px[mask], axis=0)) if mask.any() else back
    return back, ink


def render_into(size, text, font_path, box, ink, back, flush_left: bool):
    """Draw so the Korean ink lands on the original ink's left edge and baseline band."""
    image = Image.new("RGBA", size, back)
    draw = ImageDraw.Draw(image)
    want_h = box[3] - box[1] + 1
    px = want_h + 4
    while px > 6:
        font = ImageFont.truetype(str(font_path), px)
        b = draw.textbbox((0, 0), text, font=font)
        if (b[2] - b[0]) <= size[0] - box[0] - 2 and (b[3] - b[1]) <= want_h + 2:
            break
        px -= 1
    font = ImageFont.truetype(str(font_path), px)
    b = draw.textbbox((0, 0), text, font=font)
    x = box[0] - b[0] if flush_left else (size[0] - (b[2] - b[0])) / 2 - b[0]
    y = box[1] + (want_h - (b[3] - b[1])) / 2 - b[1]
    draw.text((x, y), text, font=font, fill=ink)
    return image


def write_back(data: bytearray, tex, canvas: Image.Image) -> bool:
    indices = texenc.quantise(canvas, tex.palette)
    blob = texenc.encode_indices(tex, indices)
    record = tex.index * 2 + 2
    offset = int.from_bytes(data[record * 4:record * 4 + 4], "little")
    if len(blob) != len(tex.image):
        return False
    data[offset:offset + len(blob)] = blob
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=REGULAR)
    parser.add_argument("--clean", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "stream0_ko3.bin")
    parser.add_argument("--preview", type=Path, default=ROOT / "build" / "align_v3.png")
    args = parser.parse_args()

    clean = args.clean.read_bytes()
    data = bytearray(clean)
    textures = {t.index: t for t in texpack.load_textures(clean)}

    # --- 128x32 overlays, each keeping its original alignment ---------------
    done = flush = 0
    for tex in [t for t in textures.values() if (t.width, t.height) == (128, 32)]:
        text = LABELS.get(tex.index)
        if text is None:
            continue
        px = np.asarray(texpack.decode(tex).convert("RGBA")).astype(np.int32)
        box = ink_box(px)
        if box is None:
            continue
        back, ink = colours_of(px, box)
        left = box[0] <= 3
        canvas = render_into((tex.width, tex.height), text, args.font, box, ink, back, left)
        if write_back(data, tex, canvas):
            done += 1
            flush += left
    print(f"overlays: {done} rendered, {flush} flush-left, {done - flush} centred")

    # --- panel rows, at the measured Japanese positions ---------------------
    tex = textures[278]
    original = texpack.decode(tex).convert("RGBA")
    px = np.asarray(original).astype(np.int32)
    luma = px[:, :, :3].mean(axis=2)
    strip = luma[:, 20:280]
    floor = float(np.median(strip))
    on = (np.abs(strip - floor) > 14).sum(axis=1) >= 2
    bands, start = [], None
    for y, flag in enumerate(on):
        if flag and start is None:
            start = y
        elif not flag and start is not None:
            if y - start >= 4 and start >= 70:
                bands.append((start, y - 1))
            start = None
    print(f"panel: {len(bands)} label rows at {bands}")
    if len(bands) != len(ITEMS):
        print("   row count does not match, panel left untouched")
    else:
        canvas = original.copy()
        draw = ImageDraw.Draw(canvas)
        band0 = px[bands[0][0]:bands[0][1] + 1, 20:280]
        back, ink = colours_of(band0, (0, 0, 0, 0))
        left = 36
        for (top, bottom), text in zip(bands, ITEMS):
            draw.rectangle((left - 4, top - 2, 290, bottom + 2), fill=back)
            h = bottom - top + 1
            size = h + 3
            while size > 6:
                font = ImageFont.truetype(str(args.font), size)
                b = draw.textbbox((0, 0), text, font=font)
                if (b[2] - b[0]) <= 290 - left and (b[3] - b[1]) <= h + 2:
                    break
                size -= 1
            font = ImageFont.truetype(str(args.font), size)
            b = draw.textbbox((0, 0), text, font=font)
            draw.text((left - b[0], top + (h - (b[3] - b[1])) / 2 - b[1]),
                      text, font=font, fill=ink)

        # header, same as before
        for box, lines, pt in (((6, 2, 196, 74), [TITLE], 52),
                               ((198, 4, 508, 74), BLURB, 16)):
            patch = px[box[1]:box[3], box[0]:box[2]]
            hback, hink = colours_of(patch, box)
            draw.rectangle(box, fill=hback)
            font = ImageFont.truetype(str(args.font), pt)
            if len(lines) == 1:
                b = draw.textbbox((0, 0), lines[0], font=font)
                draw.text((box[0] + 8 - b[0],
                           (box[1] + box[3]) / 2 - (b[3] + b[1]) / 2),
                          lines[0], font=font, fill=hink)
            else:
                y = box[1] + 3
                for line in lines:
                    draw.text((box[0] + 2, y), line, font=font, fill=hink)
                    y += pt + 6
        if write_back(data, tex, canvas):
            print(f"panel: written, ink {ink}, background {back}")
            shown = texpack.decode(next(
                t for t in texpack.load_textures(bytes(data)) if t.index == 278))
            side = Image.new("RGBA", (tex.width, tex.height * 2 + 6), (24, 24, 24, 255))
            side.paste(original, (0, 0), original)
            side.paste(shown, (0, tex.height + 6), shown)
            side.save(args.preview)

    args.out.write_bytes(bytes(data))
    print(f"-> {args.out}\n-> {args.preview}")


if __name__ == "__main__":
    main()

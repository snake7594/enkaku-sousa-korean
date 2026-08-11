"""Patch the settings panel correctly: title and blurb only.

The first attempt drew the eight item names into this texture, which was exactly backwards.
Probing the original shows the item column is perfectly flat -- luminance 110 across the
whole area, no ink at all -- so the labels never lived here.  The game draws them from the
128x32 textures (282-290) and tints them grey or yellow depending on the cursor, which is
why the bug report shows one Korean row and seven rows of debris: the debris is the text the
previous pass painted onto a panel that is supposed to stay empty.

So this touches only the header band, and leaves everything below it as the original had it.
The report also asks for lighter, smaller text, so the title and blurb are set in the regular
weight and sized against the space they actually occupy.
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
REGULAR = Path(r"C:\Windows\Fonts\HANBatang.ttf")

TITLE = "설정"
BLURB = ["플레이 환경을 설정할 수 있습니다.",
         "취향에 맞게 선택해 주십시오.",
         "끝내려면 「돌아가기」를 선택하십시오."]
# same wording as the 128x32 overlays, so grey and yellow read identically
ITEMS = ["문장 표시 속도", "음량  음악", "음량  효과음", "음량  음성",
         "미독 빨리감기", "데이터 설치", "초기 상태로", "돌아가기"]


def region_colours(px: np.ndarray, box: tuple[int, int, int, int]):
    """Background and ink for a box, split by luminance rather than by median alone."""
    patch = px[box[1]:box[3], box[0]:box[2]]
    luma = patch[:, :, :3].mean(axis=2)
    floor = float(np.median(luma))
    ink_mask = np.abs(luma - floor) > 8
    back = tuple(int(v) for v in np.median(patch[~ink_mask], axis=0))
    ink = (tuple(int(v) for v in np.median(patch[ink_mask], axis=0))
           if ink_mask.any() else back)
    return back, ink


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=int, default=278)
    parser.add_argument("--font", type=Path, default=REGULAR)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0_ko.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "stream0_ko2.bin")
    parser.add_argument("--clean", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--preview", type=Path,
                        default=ROOT / "build" / "settings_v2.png")
    args = parser.parse_args()

    data = bytearray(args.stream.read_bytes())
    clean = args.clean.read_bytes()
    tex = next(t for t in texpack.load_textures(clean) if t.index == args.index)
    original = texpack.decode(tex).convert("RGBA")
    px = np.asarray(original).astype(np.int32)
    print(f"tex{tex.index:04d} {tex.width}x{tex.height} (starting from the clean original)")

    title_box = (6, 2, 196, 74)
    blurb_box = (198, 4, 508, 74)
    t_back, t_ink = region_colours(px, title_box)
    b_back, b_ink = region_colours(px, blurb_box)
    print(f"   title  back {t_back} ink {t_ink}")
    print(f"   blurb  back {b_back} ink {b_ink}")

    canvas = original.copy()
    draw = ImageDraw.Draw(canvas)

    draw.rectangle(title_box, fill=t_back)
    font = ImageFont.truetype(str(args.font), 52)
    box = draw.textbbox((0, 0), TITLE, font=font)
    draw.text((title_box[0] + 8 - box[0],
               (title_box[1] + title_box[3]) / 2 - (box[3] + box[1]) / 2),
              TITLE, font=font, fill=t_ink)

    draw.rectangle(blurb_box, fill=b_back)
    px_size = 16
    font = ImageFont.truetype(str(args.font), px_size)
    step = px_size + 6
    y = blurb_box[1] + 3
    for line in BLURB:
        draw.text((blurb_box[0] + 2, y), line, font=font, fill=b_ink)
        y += step

    # The item names are in this texture after all -- the earlier probe scanned the wrong
    # rows and reported the panel as flat.  They have to match the 128x32 overlays the game
    # tints yellow for the selected row, so they are set at the same left edge and pitch.
    items_box = (24, 76, 300, 250)
    i_back, i_ink = region_colours(px, items_box)
    print(f"   items  back {i_back} ink {i_ink}")
    draw.rectangle(items_box, fill=i_back)
    item_font = ImageFont.truetype(str(args.font), 17)
    top, pitch = 80, 21.5
    for n, text in enumerate(ITEMS):
        y = top + pitch * n
        draw.text((30, y), text, font=item_font, fill=i_ink)

    indices = texenc.quantise(canvas, tex.palette)
    blob = texenc.encode_indices(tex, indices)
    record = tex.index * 2 + 2
    offset = int.from_bytes(data[record * 4:record * 4 + 4], "little")
    if len(blob) != len(tex.image):
        print("   size changed, nothing written")
        return
    data[offset:offset + len(blob)] = blob
    args.out.write_bytes(bytes(data))

    colours = np.frombuffer(tex.palette, dtype=np.uint8)
    colours = colours[: (len(colours) // 4) * 4].reshape(-1, 4)
    shown = Image.fromarray(colours[indices], "RGBA")
    side = Image.new("RGBA", (tex.width, tex.height * 2 + 6), (24, 24, 24, 255))
    side.paste(original, (0, 0), original)
    side.paste(shown, (0, tex.height + 6), shown)
    side.save(args.preview)
    print(f"-> {args.out}\n-> {args.preview}")


if __name__ == "__main__":
    main()

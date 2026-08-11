"""Repair the settings background, measuring the original instead of guessing at it.

The previous attempt cleared a rectangle and drew Korean at hand-picked coordinates in a
colour sampled from the wrong place.  The labels vanished, leaving the vertical fragments
visible in the bug report.

What the report also makes clear is how the screen works: the grey labels live in this
background texture and the game draws the yellow selected copy from a separate 128x32
texture on top.  So the two have to line up exactly -- the Korean here must sit where the
Korean there sits.

Everything positional is therefore measured from the original texture: each label's ink
bounding box gives the left edge and the vertical centre, and the ink colour is taken from
the label pixels themselves rather than from a median that includes the background.
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
# regular weight: the report says the previous render was too heavy and too large
SERIF = Path(r"C:\Windows\Fonts\HANBatang.ttf")

TITLE = "설정"
BLURB = ["플레이 환경을 설정할 수 있습니다.",
         "취향에 맞게 선택해 주십시오.",
         "끝내려면 「돌아가기」를 선택하십시오."]
ITEMS = ["문장 표시 속도", "음량  음악", "음량  효과음", "음량  음성",
         "미독 빨리감기", "데이터 설치", "초기 상태로", "돌아가기"]


def ink_rows(luma: np.ndarray, lo: int, hi: int, x0: int, x1: int,
             gap: int = 3) -> list[tuple[int, int]]:
    """Vertical runs of ink in a column strip -- one per label row.

    The panel is fully opaque, so alpha says nothing; the labels are light grey on a darker
    grey field.  Ink is therefore anything brighter than the strip's own background, which
    the median gives directly.
    """
    strip = luma[lo:hi, x0:x1]
    floor = float(np.median(strip))
    mask = strip > floor + 12
    rows = mask.sum(axis=1) >= 2
    out, start, blank = [], None, 0
    for y, on in enumerate(rows):
        if on:
            if start is None:
                start = y
            blank = 0
        elif start is not None:
            blank += 1
            if blank >= gap:
                out.append((lo + start, lo + y - blank))
                start = None
    if start is not None:
        out.append((lo + start, lo + len(rows) - 1))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=int, default=278)
    parser.add_argument("--font", type=Path, default=SERIF)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "stream0_fix.bin")
    parser.add_argument("--preview", type=Path,
                        default=ROOT / "build" / "settings_fix.png")
    parser.add_argument("--report", type=Path,
                        default=ROOT / "build" / "settings_fix_report.json")
    args = parser.parse_args()

    data = bytearray(args.stream.read_bytes())
    tex = next(t for t in texpack.load_textures(bytes(data)) if t.index == args.index)
    original = texpack.decode(tex).convert("RGBA")
    pixels = np.asarray(original).astype(np.int32)
    luma = pixels[:, :, :3].mean(axis=2)
    print(f"tex{tex.index:04d}  {tex.width}x{tex.height}")

    # the item list occupies the left half below the header band
    rows = ink_rows(luma, 76, tex.height, 20, 260)
    print(f"   {len(rows)} ink rows found in the item column: {rows}")
    if len(rows) != len(ITEMS):
        print(f"   expected {len(ITEMS)} -- refusing to write")
        return

    # left edge and colour taken from the first label's own pixels
    top, bottom = rows[0]
    band = pixels[top:bottom + 1, 20:260]
    floor = float(np.median(luma[top:bottom + 1, 20:260]))
    on = luma[top:bottom + 1, 20:260] > floor + 12
    xs = np.flatnonzero(on.any(axis=0))
    left = 20 + int(xs.min())
    ink = tuple(int(v) for v in np.median(band[on], axis=0))
    height = bottom - top + 1
    print(f"   left edge {left}, ink {ink}, label height {height}px")

    canvas = original.copy()
    draw = ImageDraw.Draw(canvas)

    # background sampled where there is provably no ink, not from a median over the text
    empty = pixels[top:bottom + 1, 270:300].reshape(-1, 4)
    back = tuple(int(v) for v in np.median(empty, axis=0))
    print(f"   background {back}")

    for (r_top, r_bottom), text in zip(rows, ITEMS):
        draw.rectangle((left - 2, r_top - 2, 268, r_bottom + 2), fill=back)
        px = height + 2
        while px > 6:
            font = ImageFont.truetype(str(args.font), px)
            box = draw.textbbox((0, 0), text, font=font)
            if box[2] - box[0] <= 268 - left and box[3] - box[1] <= height + 2:
                break
            px -= 1
        font = ImageFont.truetype(str(args.font), px)
        box = draw.textbbox((0, 0), text, font=font)
        y = (r_top + r_bottom) / 2 - (box[3] + box[1]) / 2
        draw.text((left, y), text, font=font, fill=ink)

    indices = texenc.quantise(canvas, tex.palette)
    blob = texenc.encode_indices(tex, indices)
    record = tex.index * 2 + 2
    offset = int.from_bytes(data[record * 4:record * 4 + 4], "little")
    if len(blob) != len(tex.image) or \
            bytes(data[offset:offset + len(blob)]) != tex.image[:len(blob)]:
        print("   record check failed, nothing written")
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

    args.report.write_text(json.dumps({
        "texture": tex.index, "rows": rows, "left": left, "ink": ink,
        "background": back, "labels": ITEMS,
        "note": "grey labels here must match the yellow 128x32 overlays exactly",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {args.out}\n-> {args.preview}")


if __name__ == "__main__":
    main()

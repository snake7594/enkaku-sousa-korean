"""Replace the Japanese names on the character plates.

Readings follow the names already established in the dialogue where one exists -- 三浦正信 is
미우라 마사노부 and 水谷朝露 is 미즈타니 아사츠유 throughout the script, and 新城法子 is
신조 노리코 -- so the plates agree with what the player has been reading.

Two are less certain and are marked as such rather than asserted: 吉本清香 could be 사야카 or
기요카, and 七芝伊月 could be 이즈키 or 이츠키.  Both are given the commoner reading.

The plate is text on a light band across the bottom of a portrait, so only that band is
repainted and its colours are taken from the band itself.
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

NAMES = {
    357: ("水無月葵", "미나즈키 아오이", 0.9),
    356: ("神崎茜", "간자키 아카네", 0.9),
    361: ("近藤克美", "콘도 가쓰미", 0.85),
    342: ("吉本清香", "요시모토 사야카", 0.6),
    343: ("水谷朝露", "미즈타니 아사츠유", 0.95),
    341: ("三浦正信", "미우라 마사노부", 0.95),
    359: ("マスター", "마스터", 0.95),
    351: ("新城法子", "신조 노리코", 0.95),
    349: ("白川安代", "시라카와 야스요", 0.85),
    # the game attaches the reading itself -- 七芝《ななしば》伊月《いつき》 -- so this one is
    # settled, and the plate had the commoner-looking guess rather than the game's own answer
    358: ("七芝伊月", "나나시바 이츠키", 1.0),
    339: ("吉本ユミ", "요시모토 유미", 0.9),
    # found on a second, looser pass -- the first threshold wanted more ink than a
    # three-character name puts on the band
    354: ("白川悟", "시라카와 사토루", 0.85),
    362: ("白川悟", "시라카와 사토루", 0.85),
    346: ("斉藤佳代", "사이토 가요", 0.9),
    345: ("斉藤志朗", "사이토 시로", 0.85),
    348: ("白川一朗", "시라카와 이치로", 0.95),
    344: ("白川真二", "시라카와 신지", 0.95),
    347: ("白川美佐恵", "시라카와 미사에", 0.85),
    # The second audit found these six still Japanese -- every one a plate the ink-threshold
    # pass skipped the first time round.  Readings follow the dialogue: the defendant 斉藤光志
    # and the protagonist 水無月幸司 both read こうじ and the script renders both 코우지.
    340: ("近藤克美", "콘도 가쓰미", 0.9),
    350: ("沼崎栄太郎", "누마사키 에이타로", 0.95),
    352: ("斉藤光志", "사이토 코우지", 0.95),
    353: ("白川のぞみ", "시라카와 노조미", 0.95),
    355: ("沼崎晋太郎", "누마사키 신타로", 0.95),
    360: ("水無月幸司", "미나즈키 코우지", 0.95),
}
BAND = 26


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=SERIF)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0_ko5.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "stream0_ko6.bin")
    parser.add_argument("--clean", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--preview", type=Path, default=ROOT / "build" / "nameplates_ko.png")
    parser.add_argument("--report", type=Path,
                        default=ROOT / "build" / "nameplate_report.json")
    args = parser.parse_args()

    data = bytearray(args.stream.read_bytes())
    clean = args.clean.read_bytes()
    textures = {t.index: t for t in texpack.load_textures(clean)}
    shots, done = [], []

    for index, (ja, ko, confidence) in NAMES.items():
        tex = textures.get(index)
        if tex is None:
            continue
        original = texpack.decode(tex).convert("RGBA")
        px = np.asarray(original).astype(np.int32)
        top = tex.height - BAND
        band = px[top:, :, :]
        # Only opaque pixels count.  Several plates carry a transparent margin around the
        # white band, and letting those into the median made the "background" come out white
        # with alpha 0 -- so the band was wiped to nothing and the dark name was then drawn
        # onto the portrait behind it, where it reads as a smudge.
        opaque = band[:, :, 3] > 128
        luma = band[:, :, :3].mean(axis=2)
        floor = float(np.median(luma[opaque])) if opaque.any() else 255.0
        ink_mask = opaque & (np.abs(luma - floor) > 60)
        if not ink_mask.any():
            print(f"   tex{index:04d}: no ink in the band, skipped")
            continue
        ys, xs = np.nonzero(ink_mask)
        box = (int(xs.min()), int(ys.min()) + top, int(xs.max()), int(ys.max()) + top)
        # Sample only the rows the text sits on.  Taking the median across the whole band
        # picks up the portrait above it, which turned some plates grey or yellow when the
        # original is black on white.
        text_rows = band[int(ys.min()):int(ys.max()) + 1]
        text_mask = ink_mask[int(ys.min()):int(ys.max()) + 1]
        text_opaque = opaque[int(ys.min()):int(ys.max()) + 1]
        ground = text_rows[text_opaque & ~text_mask]
        if not len(ground):
            print(f"   tex{index:04d}: no opaque ground in the band, skipped")
            continue
        back = tuple(int(v) for v in np.median(ground, axis=0))
        core = text_rows[text_mask]
        darkest = core[core[:, :3].sum(axis=1).argmin()]
        ink = tuple(int(v) for v in darkest)[:3] + (255,)

        canvas = original.copy()
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((0, box[1] - 2, tex.width - 1, box[3] + 2), fill=back)
        height = box[3] - box[1] + 1
        size = height + 3
        while size > 6:
            font = ImageFont.truetype(str(args.font), size)
            b = draw.textbbox((0, 0), ko, font=font)
            if (b[2] - b[0]) <= tex.width - 8 and (b[3] - b[1]) <= height + 2:
                break
            size -= 1
        font = ImageFont.truetype(str(args.font), size)
        b = draw.textbbox((0, 0), ko, font=font)
        draw.text(((tex.width - (b[2] - b[0])) / 2 - b[0],
                   box[1] + (height - (b[3] - b[1])) / 2 - b[1]),
                  ko, font=font, fill=ink)

        indices = texenc.quantise(canvas, tex.palette)
        blob = texenc.encode_indices(tex, indices)
        record = tex.index * 2 + 2
        offset = int.from_bytes(data[record * 4:record * 4 + 4], "little")
        if len(blob) != len(tex.image):
            print(f"   tex{index:04d}: size changed, skipped")
            continue
        data[offset:offset + len(blob)] = blob
        done.append({"index": index, "ja": ja, "ko": ko, "confidence": confidence,
                     "band": list(box), "size_px": size})
        shots.append((original.crop((0, top, tex.width, tex.height)),
                      canvas.crop((0, top, tex.width, tex.height))))
        print(f"   tex{index:04d}  {ja} -> {ko}  ({size}px, confidence {confidence})")

    args.out.write_bytes(bytes(data))
    args.report.write_text(json.dumps(
        {"schema": "enkaku_nameplates_v1", "patched": done}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    if shots:
        sc, pad = 2, 4
        w, h = shots[0][0].size
        sheet = Image.new("RGBA", (2 * (w * sc + pad) + pad,
                                   len(shots) * (h * sc + pad) + pad), (18, 18, 18, 255))
        for n, (before, after) in enumerate(shots):
            y = pad + n * (h * sc + pad)
            sheet.paste(before.resize((w * sc, h * sc), Image.NEAREST), (pad, y))
            sheet.paste(after.resize((w * sc, h * sc), Image.NEAREST), (pad * 2 + w * sc, y))
        sheet.save(args.preview)
    print(f"\n{len(done)} plates -> {args.out}\n-> {args.preview}")


if __name__ == "__main__":
    main()

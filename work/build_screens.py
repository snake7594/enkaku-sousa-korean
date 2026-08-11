"""Patch the two full-screen textures that carry baked-in Japanese.

tex0278 is the whole settings screen -- the 設定 title, the three lines of description and
all eight item names are painted into one 512x256 image.  That is why replacing the 128x32
labels left the screen in Japanese: those are the highlighted copies, and the ones actually
on screen live here.

tex0448 is the interrogation hint panel, with 尋問のヒント on the bar and 助言 watermarked
behind it.

Both are pictures, so the background is kept and only the text areas are repainted, with
colours sampled from the image rather than assumed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import texenc
import texpack

ROOT = Path(r"D:\psp\원격수사")
SERIF = Path(r"C:\Windows\Fonts\HANBatangB.ttf")

# (clear box, then the text drawn into it) in texture pixels
SETTINGS = {
    "title": ((8, 2, 196, 74), [(14, 6, 56, "설정")]),
    "blurb": ((198, 4, 510, 74), [(200, 6, 17, "플레이 환경을 설정할 수 있습니다."),
                                  (200, 27, 17, "취향에 맞게 선택해 주십시오."),
                                  (200, 48, 17, "끝내려면 「돌아가기」를 선택하십시오.")]),
    "items": ((40, 80, 300, 252), [(46, 84, 19, "문장 표시 속도"),
                                   (46, 105, 19, "음량  음악"),
                                   (46, 126, 19, "음량  효과음"),
                                   (46, 147, 19, "음량  음성"),
                                   (46, 168, 19, "미독 빨리감기"),
                                   (46, 189, 19, "데이터 설치"),
                                   (46, 210, 19, "초기 상태로"),
                                   (46, 231, 19, "돌아가기")]),
}
HINT = {"bar": ((56, 792 - 792, 440, 30), [(64, 4, 20, "심문 힌트")])}


def sample(pixels: np.ndarray, box: tuple[int, int, int, int]) -> tuple:
    patch = pixels[box[1]:box[3], box[0]:box[2]].reshape(-1, 4)
    solid = patch[patch[:, 3] > 200]
    if not len(solid):
        return (60, 60, 60, 255), (230, 230, 230, 255)
    back = tuple(int(v) for v in np.median(solid, axis=0))
    bright = solid[solid[:, :3].sum(axis=1).argmax()]
    return back, tuple(int(v) for v in bright)


def patch(data: bytearray, tex, plan: dict, font_path: Path) -> bool:
    image = texpack.decode(tex).convert("RGBA")
    pixels = np.asarray(image)
    canvas = image.copy()
    draw = ImageDraw.Draw(canvas)
    # Ink is taken from the whole image, not from each box: the item list is light text on
    # dark grey, and the brightest pixel inside that box is still dark, so sampling locally
    # produced text the same colour as its background.
    solid = pixels.reshape(-1, 4)
    solid = solid[solid[:, 3] > 200]
    ink = tuple(int(v) for v in solid[solid[:, :3].sum(axis=1).argmax()]) \
        if len(solid) else (235, 235, 235, 255)

    for box, items in plan.values():
        back, _ = sample(pixels, box)
        draw.rectangle(box, fill=back)
        for x, y, px, text in items:
            font = ImageFont.truetype(str(font_path), px)
            draw.text((x, y), text, font=font, fill=ink)

    indices = texenc.quantise(canvas, tex.palette)
    blob = texenc.encode_indices(tex, indices)
    record = tex.index * 2 + 2
    offset = int.from_bytes(data[record * 4:record * 4 + 4], "little")
    if len(blob) != len(tex.image) or \
            bytes(data[offset:offset + len(blob)]) != tex.image[:len(blob)]:
        return False
    data[offset:offset + len(blob)] = blob
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=SERIF)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0_ko.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "stream0_ko.bin")
    parser.add_argument("--preview", type=Path, default=ROOT / "build" / "screens_ko.png")
    args = parser.parse_args()

    data = bytearray(args.stream.read_bytes())
    textures = {t.index: t for t in texpack.load_textures(bytes(data))}

    for index, plan in ((278, SETTINGS), (448, HINT)):
        tex = textures.get(index)
        if tex is None:
            print(f"   tex{index:04d} missing")
            continue
        if patch(data, tex, plan, args.font):
            print(f"   tex{index:04d} patched")
        else:
            print(f"   tex{index:04d}: record check failed, stopping")
            return

    args.out.write_bytes(bytes(data))
    print(f"-> {args.out}")

    shown = texpack.load_textures(bytes(data))
    preview = next(t for t in shown if t.index == 278)
    texpack.decode(preview).save(args.preview)
    print(f"-> {args.preview}")


if __name__ == "__main__":
    main()

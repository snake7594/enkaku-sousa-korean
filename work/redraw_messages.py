"""Set the system messages again, at their real size instead of shrunk from 4x.

They were drawn four times larger and scaled back down with LANCZOS.  That is the right way
to make big type look smooth, and the wrong way to make 14-pixel type readable: the filter
spreads every stroke across two pixels at half strength, so on a PSP screen the letters come
out thin and broken.  This is what the report is about.

Drawing straight at the final size instead keeps a stroke one pixel wide and fully lit, and a
gothic face holds together at that size where a serif's thin strokes do not.  Everything else
about the textures -- position, left margin, line spacing -- is unchanged.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import texenc
import texpack

ROOT = Path(r"D:\psp\원격수사")
GOTHIC = Path(r"C:\Windows\Fonts\malgunbd.ttf")

# Rendering them side by side with the Japanese showed the previous pass had these attached
# to the wrong textures -- 429 carried the message for 432, 431 the one for 435, and so on.
# Each entry below sits against the Japanese that is actually in that texture.
MESSAGES = {
    # インストールデータをロードできませんでした。
    428: "설치 데이터를 불러올 수 없었습니다.\n데이터 설치 기능을 《사용 안 함》으로 설정했습니다.",
    # インストールデータが破損しています。… 再度、データインストールを行ってください。
    429: "설치 데이터가 손상되었습니다.\n데이터 설치 기능을 《사용 안 함》으로 설정했습니다.\n"
         "다시 데이터 설치를 해 주십시오.",
    # インストールデータをロードできませんでした。 (428 と同じ文面)
    430: "설치 데이터를 불러올 수 없었습니다.\n데이터 설치 기능을 《사용 안 함》으로 설정했습니다.",
    # インストールデータがセーブされています。データインストールの機能を使用しますか？
    431: "설치 데이터가 저장되어 있습니다.\n데이터 설치 기능을 사용하시겠습니까?",
    # インストールデータがセーブされていません。
    432: "설치 데이터가 저장되어 있지 않습니다.\n데이터 설치 기능을 《사용 안 함》으로 설정했습니다.",
    # 遠隔捜査のセーブデータを保存するには 320KB以上の空き容量が必要です。
    435: "원격수사의 저장 데이터를 보관하려면\n320KB 이상의 빈 용량이 필요합니다.\n"
         "저장 데이터를 삭제하시겠습니까?",
}


def render(text: str, size: tuple[int, int], font_path: Path, start: int) -> Image.Image:
    image = Image.new("RGBA", size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    lines = text.split("\n")
    px = start
    while px > 8:
        font = ImageFont.truetype(str(font_path), px)
        widest = max(draw.textlength(line, font=font) for line in lines)
        if widest <= size[0] - 10 and (px + 3) * len(lines) <= size[1]:
            break
        px -= 1
    font = ImageFont.truetype(str(font_path), px)
    step = px + 3
    y = (size[1] - step * len(lines)) / 2
    for line in lines:
        draw.text((6, y), line, font=font, fill=(255, 255, 255, 255))
        y += step
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0_ko16.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "stream0_ko17.bin")
    parser.add_argument("--font", type=Path, default=GOTHIC)
    parser.add_argument("--size", type=int, default=15)
    parser.add_argument("--preview", type=Path, default=ROOT / "build" / "messages_ko.png")
    args = parser.parse_args()

    data = bytearray(args.stream.read_bytes())
    textures = {t.index: t for t in texpack.load_textures(args.clean.read_bytes())}
    shots, done = [], []

    for index, text in MESSAGES.items():
        tex = textures.get(index)
        if tex is None:
            continue
        image = render(text, (tex.width, tex.height), args.font, args.size)
        blob = texenc.encode_indices(tex, texenc.quantise(image, tex.palette))
        record = tex.index * 2 + 2
        offset = int.from_bytes(data[record * 4:record * 4 + 4], "little")
        if len(blob) != len(tex.image):
            print(f"   tex{index:04d}: size changed, skipped")
            continue
        data[offset:offset + len(blob)] = blob
        done.append(index)
        shots.append((index, texpack.decode(tex).convert("RGBA"), image))
        print(f"   tex{index:04d}  {text.splitlines()[0][:40]}")

    args.out.write_bytes(bytes(data))
    if shots:
        w = max(a.width for _, a, _ in shots)
        h = sum(a.height * 2 + 8 for _, a, _ in shots) + 8
        sheet = Image.new("RGBA", (w + 8, h), (18, 18, 28, 255))
        y = 4
        for _, before, after in shots:
            for image in (before, after):
                bg = Image.new("RGBA", image.size, (18, 18, 28, 255))
                sheet.paste(Image.alpha_composite(bg, image), (4, y))
                y += image.height + 2
            y += 6
        sheet.convert("RGB").save(args.preview)
    print(f"\n{len(done)} messages -> {args.out}\n-> {args.preview}")


if __name__ == "__main__":
    main()

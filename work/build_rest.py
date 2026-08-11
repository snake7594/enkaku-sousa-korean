"""Render the place names, relationship labels and system messages.

These three groups are ordinary label textures -- one string per image, fixed size -- so they
go through the same fit-to-box path as the menu. They are kept in one file because they are
the last of the straightforward ones; what remains after this is the 256x64 HUD atlas, where
several strings share one texture and each has a fixed slot, and the notebook, which is
handwriting.

Entries are keyed by index. An index with no entry is left in Japanese rather than guessed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

import texenc
import texpack
from build_menu_textures import fit

ROOT = Path(r"D:\psp\원격수사")
SERIF = Path(r"C:\Windows\Fonts\HANBatangB.ttf")

# 128x16 -- place names, in index order 395, 416-425
PLACES = ["돌아가기", "시라카와 저택", "시라카와 빌딩", "미즈타니 탐정사무소",
          "라이트 블루", "누마자키 법률사무소", "포레스트 하임", "수도 택시 센터",
          "미야카미대 부속병원", "어뮤즈 하우스", "오인고교"]

# 64x32 -- relationship labels, in index order
RELATIONS = ["옛 연인", "부부", "전 부부", "부모자식", "사촌", "친구",
             "자매", "남매", "형제", "대립", "동거인", "기증자"]

# 512x64 -- system messages; only the six that carry text
MESSAGES = {
    428: "설치 데이터를 불러올 수 없었습니다.\n데이터 설치 기능을 《사용 안 함》으로 설정했습니다.",
    429: "설치 데이터가 저장되어 있지 않습니다.\n데이터 설치 기능을 《사용 안 함》으로 설정했습니다.",
    430: "설치 데이터가 손상되었습니다.\n데이터 설치 기능을 《사용 안 함》으로 설정했습니다.\n다시 데이터 설치를 해 주십시오.",
    431: "원격수사의 저장 데이터를 보관하려면\n320KB 이상의 빈 용량이 필요합니다.\n저장 데이터를 삭제하시겠습니까?",
    432: "설치 데이터를 불러올 수 없었습니다.\n데이터 설치 기능을 《사용 안 함》으로 설정했습니다.",
    435: "설치 데이터가 저장되어 있습니다.\n데이터 설치 기능을 사용하시겠습니까?",
}


def draw_lines(text: str, size: tuple[int, int], font_path: Path,
               px: int) -> Image.Image:
    """Multi-line messages are set line by line, left-aligned like the originals."""
    from PIL import ImageDraw, ImageFont
    scale = 4
    big = Image.new("RGBA", (size[0] * scale, size[1] * scale), (255, 255, 255, 0))
    draw = ImageDraw.Draw(big)
    lines = text.split("\n")
    while px > 6:
        font = ImageFont.truetype(str(font_path), px * scale)
        widest = max(draw.textlength(l, font=font) for l in lines)
        if widest <= (size[0] - 8) * scale and (px + 2) * len(lines) <= size[1]:
            break
        px -= 1
    font = ImageFont.truetype(str(font_path), px * scale)
    step = (px + 2) * scale
    y = (big.height - step * len(lines)) / 2
    for line in lines:
        draw.text((6 * scale, y), line, font=font, fill=(255, 255, 255, 255))
        y += step
    return big.resize(size, Image.LANCZOS)


def write(data: bytearray, tex, image: Image.Image) -> bool:
    indices = texenc.quantise(image, tex.palette)
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
    args = parser.parse_args()

    data = bytearray(args.stream.read_bytes())
    textures = texpack.load_textures(bytes(data))
    groups = {size: [t for t in textures if (t.width, t.height) == size]
              for size in ((128, 16), (64, 32), (512, 64))}

    done = 0
    for size, labels, px in (((128, 16), PLACES, 11), ((64, 32), RELATIONS, 15)):
        group = groups[size]
        if len(group) != len(labels):
            print(f"   {size}: {len(group)} textures vs {len(labels)} labels -- skipped")
            continue
        for tex, text in zip(group, labels):
            image = fit(text, size, args.font, px, 0)
            if write(data, tex, image):
                done += 1
            else:
                print(f"   tex{tex.index:04d}: record check failed")
                return
        print(f"   {size[0]}x{size[1]}: {len(labels)} written")

    for tex in groups[(512, 64)]:
        text = MESSAGES.get(tex.index)
        if text is None:
            continue
        if write(data, tex, draw_lines(text, (tex.width, tex.height), args.font, 14)):
            done += 1
        else:
            print(f"   tex{tex.index:04d}: record check failed")
            return
    print(f"   512x64: {len(MESSAGES)} written")

    args.out.write_bytes(bytes(data))
    print(f"{done} textures written -> {args.out}")


if __name__ == "__main__":
    main()

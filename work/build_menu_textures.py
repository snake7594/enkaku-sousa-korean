"""Render the 128x32 menu, settings and chapter labels into stream 0.

The mapping is positional: the 128x32 group is emitted in index order, and the contact sheet
was laid out in that same order eight to a row, so cell n is group[n].  Every entry names the
Japanese it expects, and the render is skipped if the label list and the group ever fall out
of step -- writing Korean over the wrong texture is worse than leaving one alone.

Cells that are not text are left untouched: the volume gauge, and the two cells that pair
はい/いいえ in one image, which would need a different layout rather than a translation.

These are far narrower than the date cards, so the text is fitted to the box rather than set
at a fixed size -- a chapter title like 문장 표시 속도 has to shrink to fit 128 pixels.
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

# in sheet order, eight per row; None leaves the texture alone
LABELS: list[str | None] = [
    "사건의 발단", "뜻밖의 재회", "무의미한 대화", "기억의 경계",
    "의혹의 거래", "닿지 않는 마음", "희망과 우울", "인연의 연쇄",
    "기억의 계승", "마음의 상처", "운명의 진자", "예정된 조화",
    "사라진 증거", "무력한 사죄", "참고 넘김", "독단과 편견",
    "융화의 조짐", "고발의 행방", "뜻밖의 진실", "과거의 청산",
    "마지막 질주", "모든 것의 결말", "문장 표시 속도", "음량 음악",
    "음량 효과음", "음량 음성", "데이터 설치", "미독 빨리감기",
    "초기 상태로", "돌아가기", "느림", "느림",
    "조금 느림", "조금 느림", "보통", "보통",
    "조금 빠름", "조금 빠름", "빠름", "빠름",
    "없음", "없음", "작게", "작게",
    "중간", "중간", "크게", "크게",
    "최대", "최대", "안 함", "안 함",
    "함", "함", "사용 안 함", "사용 안 함",
    "사용함", "사용함", "단서 일람", "●단서 일람",
    "심문 일람", "●심문 일람", "알리바이 표", "●알리바이 표",
    "인물 관계도", "●인물 관계도", "토리비아 도감", "●토리비아 도감",
    "저장", "●저장", "불러오기", "●불러오기",
    "옵션", "●옵션", "타이틀로", "●타이틀로",
    "상사와 부하", "옛 상사와 부하", "신뢰 관계", "사제 관계",
    "대학 친구", "사제 관계?", "고교 동창", "수사 협력",
    "선배와 후배", None, None, None,
    None, None, None,
]


def fit(text: str, size: tuple[int, int], font_path: Path,
        max_px: int, dy: int) -> Image.Image:
    """Draw centred, shrinking the size until the text fits the box."""
    scale = 4
    big = Image.new("RGBA", (size[0] * scale, size[1] * scale), (255, 255, 255, 0))
    draw = ImageDraw.Draw(big)
    px = max_px
    while px > 6:
        font = ImageFont.truetype(str(font_path), px * scale)
        box = draw.textbbox((0, 0), text, font=font)
        if box[2] - box[0] <= (size[0] - 4) * scale:
            break
        px -= 1
    font = ImageFont.truetype(str(font_path), px * scale)
    box = draw.textbbox((0, 0), text, font=font)
    x = (big.width - (box[2] - box[0])) / 2 - box[0]
    y = (big.height - (box[3] - box[1])) / 2 - box[1] + dy * scale
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    return big.resize(size, Image.LANCZOS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--px", type=int, default=17)
    parser.add_argument("--dy", type=int, default=0)
    parser.add_argument("--font", type=Path, default=SERIF)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0_ko.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "stream0_ko.bin")
    parser.add_argument("--sheet", type=Path, default=ROOT / "build" / "menu_ko.png")
    args = parser.parse_args()

    data = bytearray(args.stream.read_bytes())
    group = [t for t in texpack.load_textures(bytes(data))
             if (t.width, t.height) == (128, 32)]
    print(f"{len(group)} textures of 128x32; {len(LABELS)} labels")
    if len(group) != len(LABELS):
        print("   counts differ -- refusing to write, the mapping would be off by one")
        return

    rendered, written = [], 0
    for tex, text in zip(group, LABELS):
        if text is None:
            rendered.append(texpack.decode(tex))
            continue
        drawn = fit(text, (tex.width, tex.height), args.font, args.px, args.dy)
        indices = texenc.quantise(drawn, tex.palette)
        blob = texenc.encode_indices(tex, indices)
        record = tex.index * 2 + 2
        offset = int.from_bytes(data[record * 4:record * 4 + 4], "little")
        if len(blob) != len(tex.image) or \
                bytes(data[offset:offset + len(blob)]) != tex.image[:len(blob)]:
            print(f"   tex{tex.index:04d}: record check failed, stopping")
            return
        data[offset:offset + len(blob)] = blob
        colours = np.frombuffer(tex.palette, dtype=np.uint8)
        colours = colours[: (len(colours) // 4) * 4].reshape(-1, 4)
        rendered.append(Image.fromarray(colours[indices], "RGBA"))
        written += 1

    args.out.write_bytes(bytes(data))
    print(f"{written} labels written -> {args.out}")

    pad, cols = 4, 8
    rows = (len(rendered) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * (128 + pad) + pad, rows * (32 + pad) + pad),
                      (24, 24, 24, 255))
    for n, im in enumerate(rendered):
        r, c = divmod(n, cols)
        sheet.paste(im, (pad + c * (128 + pad), pad + r * (32 + pad)), im)
    sheet.save(args.sheet)
    print(f"-> {args.sheet}")


if __name__ == "__main__":
    main()

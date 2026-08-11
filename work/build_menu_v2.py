"""Re-render the 128x32 menu labels, keyed by texture index.

The first pass mapped them by position in the contact sheet and got the values right but the
labels wrong: the indices are not consecutive -- 1-22, then 282-336, then 363-382, with gaps
-- so the nth image on the sheet is not the nth index.  On screen that showed up as Korean
values beside Japanese labels, and a stray 돌아가기 drawn over 戻る.

Keyed by index, a gap in the numbering costs nothing and an entry that is missing simply
leaves that texture in Japanese.
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

LABELS: dict[int, str] = {
    1: "사건의 발단", 2: "뜻밖의 재회", 3: "무의미한 대화", 4: "기억의 경계",
    5: "의혹의 거래", 6: "닿지 않는 마음", 7: "희망과 우울", 8: "인연의 연쇄",
    9: "기억의 계승", 10: "마음의 상처", 11: "운명의 진자", 12: "예정된 조화",
    13: "사라진 증거", 14: "무력한 사죄", 15: "참고 넘김", 16: "독단과 편견",
    17: "융화의 조짐", 18: "고발의 행방", 19: "뜻밖의 진실", 20: "과거의 청산",
    21: "마지막 질주", 22: "모든 것의 결말",
    282: "문장 표시 속도", 283: "음량  음악", 284: "음량  효과음", 285: "음량  음성",
    286: "데이터 설치", 288: "미독 빨리감기", 289: "초기 상태로", 290: "돌아가기",
    291: "느림", 292: "느림", 293: "조금 느림", 294: "조금 느림",
    295: "보통", 296: "보통", 297: "조금 빠름", 298: "조금 빠름",
    299: "빠름", 300: "빠름", 301: "없음", 302: "없음",
    303: "작게", 304: "작게", 305: "중간", 306: "중간",
    307: "크게", 308: "크게", 309: "최대", 310: "최대",
    311: "안 함", 312: "안 함", 313: "함", 314: "함",
    315: "사용 안 함", 316: "사용 안 함", 317: "사용함", 318: "사용함",
    319: "단서 일람", 320: "●단서 일람", 321: "심문 일람", 322: "●심문 일람",
    323: "알리바이 표", 324: "●알리바이 표", 325: "인물 관계도", 326: "●인물 관계도",
    327: "토리비아 도감", 328: "●토리비아 도감", 329: "저장", 330: "●저장",
    331: "불러오기", 332: "●불러오기", 333: "옵션", 334: "●옵션",
    335: "타이틀로", 336: "●타이틀로",
    363: "상사와 부하", 364: "옛 상사와 부하", 365: "신뢰 관계", 366: "사제 관계",
    372: "대학 친구", 374: "사제 관계?", 379: "고교 동창", 381: "수사 협력",
    382: "선배와 후배",
    # 396 gauge, 412 gradient, 436 はい/いいえ pair, 443/445/447 Ending No.N -- left alone
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--px", type=int, default=17)
    parser.add_argument("--dy", type=int, default=0)
    parser.add_argument("--font", type=Path, default=SERIF)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "stream0_ko.bin")
    parser.add_argument("--sheet", type=Path, default=ROOT / "build" / "menu_v2.png")
    args = parser.parse_args()

    data = bytearray(args.stream.read_bytes())
    group = [t for t in texpack.load_textures(bytes(data))
             if (t.width, t.height) == (128, 32)]
    print(f"{len(group)} textures, {len(LABELS)} labelled")

    rendered, written = [], 0
    for tex in group:
        text = LABELS.get(tex.index)
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

    pad, cols = 4, 6
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

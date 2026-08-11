"""Render the 512x32 investigation questions, keyed by texture index.

Keyed by index rather than by position: the strips are read a page at a time and this file
grows as pages are transcribed, so a positional list would silently shift every time an
entry was added.  An index that is absent is left in Japanese rather than guessed at.

Text is fitted to the box the way the menu labels are -- Korean renders wider than the
Japanese here, and a question like `살인을 저지르지 않은 근거를 대라!` has to shrink slightly
rather than run off the edge.
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

QUESTIONS: dict[int, str] = {
    188: "네가 죽인 것은 누구지?",
    189: "이번 사건의 피해자는?",
    190: "살해 시각에 무엇을 하고 있었나?",
    191: "코우지의 승차 기록이 없는 이유는?",
    192: "권총에 지문이 남아 있는 이유는?",
    193: "권총을 눈치채지 못한 이유는?",
    194: "피해자와 말다툼했나?",
    195: "VIP 룸에 들어가지 않은 증거",
    196: "취해 있었다는 객관적인 증거",
    197: "명함이 보여주는 피해자와의 관계",
    198: "VIP 룸에 들어간 젊은 남자는?",
    199: "아버지의 수기를 보지 않은 증거",
    200: "계획 살인인 이유는…",
    201: "코우지의 모호한 알리바이",
    202: "살인을 저지르지 않은 근거를 대라!",
    203: "이 사건의 진범은 누구냐!?",
    # p1 (204-219)
    204: "미즈타니 아사츠유가 진범이라 보는 이유는?",
    205: "권총의 지문은 어디서 묻었나?",
    206: "누마자키 에이타로가 진범이라 보는 이유는?",
    207: "콘도 형사가 진범이라 보는 이유는?",
    208: "미나즈키 코우지가 진범이라 보는 이유는?",
    209: "그 인물이 진범이라 보는 이유는?",
    210: "누마자키 에이타로는 무엇을 하고 있었나?",
    211: "거짓 알리바이를 신고한 이유는?",
    212: "미즈타니 아사츠유는 무엇을 하고 있었나?",
    213: "미즈타니 아사츠유의 알리바이를 증명할 수 있나",
    214: "미나즈키 코우지는 무엇을 하고 있었나?",
    215: "미나즈키 코우지의 알리바이를 증명할 수 있나",
    216: "소녀의 정체는?",
    217: "총성과 BGM으로 추리할 수 있는 사실은?",
    218: "지문을 닦아낼 필요가 없다는 근거는…",
    219: "플레이어 받침에 난 흠집과 관계된 정보는…",
    # p2 (220-235)
    220: "외부 음원을 연결했을 경우의 모순은?",
    221: "총성과 BGM으로 추리할 수 있는 사실은?",
    222: "총성의 위화감을 보여주는 정보는…",
    223: "그녀의 정체와 눈물의 이유는…",
    224: "미즈타니 아사츠유의 옛 직업은…",
    225: "콘도의 신경 쓰이는 행동은…",
    226: "짐에 손대지 않았다는 증거는?",
    227: "플레이어의 입력을 전환하려면?",
    228: "미나즈키 코우지가 최근 잃은 것은…?",
    229: "졸업 후에도 이어지는 두 사람의 관계를 보여주는 것은?",
    230: "심장 이식 수술을 받은 두 인물은…",
    231: "누마자키 변호사의 약점은…",
    232: "아사츠유가 쥔 콘도의 약점은…",
    233: "누마자키 변호사의 증언과 모순되는 정보는…",
    234: "자매라는 관계에서 정체가 드러나는 인물은…",
    235: "피해자는 두 사람의 불륜 관계를 알고 있었다…",
    # p3 (236-250)
    236: "수상하다고 보는 인물은…",
    237: "정장을 입고 있던 두 인물은?",
    238: "이 그림자의 인물은 누구라고 보나?",
    239: "사람 그림자가 콘도 형사라고 보는 근거는…",
    240: "누마자키가 증언한 알리바이의 장소는?",
    241: "시라카와가 죽인 남자는…",
    242: "가요가 말다툼하던 남성은…",
    243: "수수께끼의 남자의 정체는…",
    244: "요시모토 형사에게 묻고 싶은 것은?",
    245: "아사츠유가 찾고 있던 인물은…",
    246: "코우지를 취하게 만든 이유는?",
    247: "가게 안에 울린 총성의 정체는…",
    248: "라이트 블루에 온 예상 밖의 두 사람은…",
    249: "미즈타니 아사츠유의 범행 동기는…",
    250: "종업원 사이에서 문제가 되던 것은?",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--px", type=int, default=22)
    parser.add_argument("--dy", type=int, default=0)
    parser.add_argument("--font", type=Path, default=SERIF)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0_ko.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "stream0_ko.bin")
    parser.add_argument("--sheet", type=Path, default=ROOT / "build" / "questions_ko.png")
    args = parser.parse_args()

    data = bytearray(args.stream.read_bytes())
    group = [t for t in texpack.load_textures(bytes(data))
             if (t.width, t.height) == (512, 32)]
    print(f"{len(group)} question strips, {len(QUESTIONS)} translated")

    rendered, written = [], 0
    for tex in group:
        text = QUESTIONS.get(tex.index)
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
    print(f"{written} questions written, {len(group) - written} left in Japanese")
    print(f"-> {args.out}")

    pad = 2
    sheet = Image.new("RGBA", (512 + pad * 2, len(rendered) * (32 + pad) + pad),
                      (20, 20, 20, 255))
    for n, im in enumerate(rendered):
        sheet.paste(im, (pad, pad + n * (32 + pad)), im)
    sheet.save(args.sheet)
    print(f"-> {args.sheet}")


if __name__ == "__main__":
    main()

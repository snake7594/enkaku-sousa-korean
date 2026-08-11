"""원격수사 스크립트 텍스트 디코더.

인코딩 (확정)
-------------
    0x00-0x1F   제어 코드 (0x07 0x1C = 텍스트 시작, 0x12 0x10 = 종료, 0x11 = 개행 등)
    0x28-0x7A   히라가나 1바이트.  index = code - 0x28,  ぁ..ん (83자) 오십음도 순
    0x81 xx     Shift-JIS 그대로인 약물 (、。【】…？！（） 등)
    0x88-0x8D   한자 2바이트.  글리프 인덱스 = (lead - 0x88) * 253 + trail
    그 외 상위값 카타카나 1바이트 (아래 --kata-base 로 탐색)

한자는 유니코드가 아니라 게임 전용 글리프 인덱스라서 문자로 환원할 수 없다.
따라서 한자는 `[n]` 형태로 인덱스를 그대로 출력하고, 필요하면 폰트로 렌더링해 확인한다.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

HIRA = ("ぁあぃいぅうぇえぉおかがきぎくぐけげこごさざしじすずせぜそぞ"
        "ただちぢっつづてでとどなにぬねのはばぱひびぴふぶぷへべぺほぼぽ"
        "まみむめもゃやゅゆょよらりるれろゎわゐゑをん")
KATA = ("ァアィイゥウェエォオカガキギクグケゲコゴサザシジスズセゼソゾ"
        "タダチヂッツヅテデトドナニヌネノハバパヒビピフブプヘベペホボポ"
        "マミムメモャヤュユョヨラリルレロヮワヰヱヲンヴヵヶ")

# JIS X 0201 0xA1..0xDF, mapped to the full-width characters the game actually draws
HALFWIDTH = ("。「」、・ヲァィゥェォャュョッーアイウエオカキクケコサシスセソ"
             "タチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワン゛゜")

HIRA_BASE = 0x28
LEAD_LO, LEAD_HI = 0x81, 0x8D
KANJI_LO, KANJI_HI = 0x88, 0x8D

# Glyphs are packed 253 per lead byte, not 256: trail values 0xFD-0xFF are never
# emitted, and the table is contiguous rather than leaving gaps.  Confirmed in game —
# codes with lead 0x89+ drew the glyph at (lead-0x88)*253+trail, not *256.
GLYPHS_PER_LEAD = 253


def kanji_index(lead: int, trail: int) -> int:
    return (lead - KANJI_LO) * GLYPHS_PER_LEAD + trail


def kanji_code(index: int) -> bytes:
    return bytes([KANJI_LO + index // GLYPHS_PER_LEAD, index % GLYPHS_PER_LEAD])

# control bytes that carry one operand byte (ruby / inline markup)
OPERAND_CONTROLS = {0x0F, 0x16}

SMALL_Y = set("ゃゅょャュョ")
I_ROW = set("きしちにひみりぎじぢびぴキシチニヒミリギジヂビピ")
SOKUON = set("っッ")
AFTER_SOKUON = set("かきくけこさしすせそたちつてとはひふへほぱぴぷぺぽ"
                   "カキクケコサシスセソタチツテトハヒフヘホパピプペポ")

STREAM = Path(r"D:\psp\원격수사\font_extract\script_stream.bin")


def text_spans(data: bytes) -> list[tuple[int, bytes]]:
    spans = []
    pos = 0
    while True:
        start = data.find(b"\x07\x1c", pos)
        if start < 0:
            break
        end = data.find(b"\x12\x10", start + 2)
        if end < 0:
            break
        if 4 < end - start < 4096:
            spans.append((start + 2, data[start + 2 : end]))
        pos = end + 2
    return spans


def decode(span: bytes, kata_base: int, kanji: str = "glyph") -> str:
    out = []
    i = 0
    n = len(span)
    in_ruby = False
    while i < n:
        b = span[i]
        if b < 0x20:
            if b == 0x11:
                out.append("\n")
            elif b == 0x0F:
                # ruby: 0F <ASCII digit n> <reading> 0F, annotating the n chars before.
                # The digit range overlaps the kana codes お..げ, so the closing tag is
                # identified by state rather than by looking at the next byte.
                if not in_ruby:
                    out.append("《")
                    in_ruby = True
                    i += 2
                    continue
                out.append("》")
                in_ruby = False
            elif b == 0x16:
                i += 2      # inline markup tag with one operand
                continue
            i += 1
            continue
        if LEAD_LO <= b <= LEAD_HI and i + 1 < n:
            trail = span[i + 1]
            if KANJI_LO <= b <= KANJI_HI:
                index = kanji_index(b, trail)
                out.append(f"[{index}]" if kanji == "glyph" else "\u25a1")
            else:
                try:
                    out.append(bytes([b, trail]).decode("cp932"))
                except Exception:  # noqa: BLE001
                    out.append(f"<{b:02x}{trail:02x}>")
            i += 2
            continue
        if HIRA_BASE <= b < HIRA_BASE + len(HIRA):
            out.append(HIRA[b - HIRA_BASE])
        elif 0xA1 <= b <= 0xDF:
            # JIS X 0201 half-width katakana, drawn full-width by the game
            out.append(HALFWIDTH[b - 0xA1])
        else:
            out.append(f"<{b:02x}>")
        i += 1
    return "".join(out)


def rule_score(text: str) -> float:
    ok = total = 0
    for i, ch in enumerate(text):
        if ch in SMALL_Y:
            total += 1
            ok += 1 if i and text[i - 1] in I_ROW else 0
        elif ch in SOKUON:
            total += 1
            ok += 1 if i + 1 < len(text) and text[i + 1] in AFTER_SOKUON else 0
    return ok / total if total >= 20 else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kata-base", type=lambda v: int(v, 0), default=None,
                        help="omit to search for it")
    parser.add_argument("--lines", type=int, default=20)
    parser.add_argument("--skip", type=int, default=0)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    data = STREAM.read_bytes()
    spans = text_spans(data)
    print(f"{len(spans)} text spans")

    kata_base = args.kata_base
    if kata_base is None:
        sample = [s for _, s in spans[:3000]]
        best = []
        for base in range(0x7B, 0x100 - len(KATA) + 1):
            text = "\n".join(decode(s, base) for s in sample)
            unknown = text.count("<") / max(1, len(text))
            best.append((rule_score(text) * (1 - unknown), base, rule_score(text), unknown))
        best.sort(reverse=True)
        print("katakana base candidates:")
        for total, base, rules, unknown in best[:5]:
            print(f"   0x{base:02x}  score={total:.3f} rules={rules:.3f} unknown={unknown:.3f}")
        kata_base = best[0][1]
    print(f"\nusing katakana base 0x{kata_base:02x}\n")

    for _, span in spans[args.skip : args.skip + args.lines]:
        print("  " + decode(span, kata_base).replace("\n", " / "))

    if args.out:
        with args.out.open("w", encoding="utf-8") as fh:
            for offset, span in spans:
                fh.write(f"0x{offset:08x}\t{decode(span, kata_base)}\n".replace("\n\t", "\t"))
        print(f"\nfull script -> {args.out}")


if __name__ == "__main__":
    main()

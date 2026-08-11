"""Solve the single-byte kana mapping by brute force over a linear offset.

The kana glyph table in BOOT.BIN is in ordinary gojūon order, so if the codes are
also linear the whole mapping is one unknown offset.  Candidate offsets are scored
with two hard rules of Japanese orthography:

  * small ゃ/ゅ/ょ (and ャ/ュ/ョ) only ever follow an i-row kana
  * っ/ッ only ever precedes a voiceless consonant kana

A wrong offset breaks both almost everywhere, so the correct one wins by a mile.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

STREAM = Path(r"D:\psp\원격수사\font_extract\script_stream.bin")

HIRA = ("ぁあぃいぅうぇえぉおかがきぎくぐけげこごさざしじすずせぜそぞ"
        "ただちぢっつづてでとどなにぬねのはばぱひびぴふぶぷへべぺほぼぽ"
        "まみむめもゃやゅゆょよらりるれろゎわゐゑをん")
KATA = ("ァアィイゥウェエォオカガキギクグケゲコゴサザシジスズセゼソゾ"
        "タダチヂッツヅテデトドナニヌネノハバパヒビピフブプヘベペホボポ"
        "マミムメモャヤュユョヨラリルレロヮワヰヱヲンヴヵヶ")
KANA = HIRA + KATA

SMALL_Y = set("ゃゅょャュョ")
I_ROW = set("きしちにひみりぎじぢびぴキシチニヒミリギジヂビピ")
SOKUON = set("っッ")
AFTER_SOKUON = set("かきくけこさしすせそたちつてとぱぴぷぺぽはひふへほカキクケコサシスセソタチツテトパピプペポハヒフヘホ")

LEAD_LO, LEAD_HI = 0x81, 0x8D
CONTROL_MAX = 0x20


def text_spans(data: bytes) -> list[tuple[int, bytes]]:
    """Byte ranges between the 07 1c text-open marker and the 12 10 close marker."""
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


def single_bytes(span: bytes) -> list[int]:
    out = []
    i = 0
    while i < len(span):
        b = span[i]
        if LEAD_LO <= b <= LEAD_HI:
            i += 2
            continue
        if b < CONTROL_MAX:
            i += 1
            continue
        out.append(b)
        i += 1
    return out


def decode_run(codes: list[int], delta: int) -> str:
    chars = []
    for code in codes:
        index = code - delta
        chars.append(KANA[index] if 0 <= index < len(KANA) else "\uffff")
    return "".join(chars)


def score(text: str) -> tuple[float, int, int]:
    small_ok = small_total = 0
    soku_ok = soku_total = 0
    for i, ch in enumerate(text):
        if ch in SMALL_Y:
            small_total += 1
            if i and text[i - 1] in I_ROW:
                small_ok += 1
        elif ch in SOKUON:
            soku_total += 1
            if i + 1 < len(text) and text[i + 1] in AFTER_SOKUON:
                soku_ok += 1
    if small_total + soku_total < 20:
        return (0.0, small_total, soku_total)
    ratio = (small_ok + soku_ok) / (small_total + soku_total)
    return (ratio, small_total, soku_total)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spans", type=int, default=4000)
    parser.add_argument("--top", type=int, default=6)
    args = parser.parse_args()

    data = STREAM.read_bytes()
    spans = text_spans(data)
    print(f"{len(spans)} text spans found")
    sample = spans[: args.spans]
    runs = [single_bytes(span) for _, span in sample]
    coverage = Counter(b for run in runs for b in run)
    print(f"{sum(coverage.values())} single-byte codes, {len(coverage)} distinct, "
          f"range 0x{min(coverage):02x}-0x{max(coverage):02x}")
    print("most common:", [(f"{b:02x}", n) for b, n in coverage.most_common(12)])

    results = []
    for delta in range(min(coverage) - len(KANA), max(coverage) + 1):
        text = "\n".join(decode_run(run, delta) for run in runs)
        ratio, small_total, soku_total = score(text)
        unmapped = text.count("\uffff") / max(1, len(text))
        results.append((ratio * (1 - unmapped), ratio, unmapped, small_total, soku_total, delta))

    results.sort(reverse=True)
    print("\nbest offsets:")
    for total, ratio, unmapped, small_total, soku_total, delta in results[: args.top]:
        print(f"   delta 0x{delta:02x} ({delta:4d})  score={total:.3f} rule_ok={ratio:.3f} "
              f"unmapped={unmapped:.3f}  small={small_total} sokuon={soku_total}")

    best_delta = results[0][5]
    print(f"\nsample decode with delta 0x{best_delta:02x} (kana only, kanji shown as ·):")
    for _, span in sample[:12]:
        chars = []
        i = 0
        while i < len(span):
            b = span[i]
            if LEAD_LO <= b <= LEAD_HI:
                chars.append("·")
                i += 2
            elif b < CONTROL_MAX:
                i += 1
            else:
                index = b - best_delta
                chars.append(KANA[index] if 0 <= index < len(KANA) else "?")
                i += 1
        print("   " + "".join(chars))


if __name__ == "__main__":
    main()

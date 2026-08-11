"""Find the screenshot line 「オレ、逮捕されたんだっけ……」 to anchor the kana mapping.

Shape we are looking for, using what is already proven:
    <k><k>          オ レ            two single-byte kana
    81 41           、
    88xx 88xx       逮 捕            two-byte kanji codes
    <k>*7           されたんだっけ    seven single-byte kana
    81 63 81 63     ……
That pattern is specific enough that a hit gives us the codes for オ and レ, and
for さ/れ/た/ん/だ/っ/け, all at once.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from decode_script import kanji_index

STREAM = Path(r"D:\psp\원격수사\font_extract\script_stream.bin")

LEAD_LO, LEAD_HI = 0x81, 0x8D
CONTROL_MAX = 0x20


def is_kana(b: int) -> bool:
    return CONTROL_MAX <= b < LEAD_LO or b > LEAD_HI


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kanji", type=int, default=2, help="kanji codes after the comma")
    parser.add_argument("--kana-after", type=int, default=7)
    parser.add_argument("--kana-before", type=int, default=2)
    parser.add_argument("--max", type=int, default=12)
    args = parser.parse_args()

    data = STREAM.read_bytes()
    hits = 0
    pos = 0
    while hits < args.max:
        i = data.find(b"\x81\x41", pos)
        if i < 0:
            break
        pos = i + 2

        # before: N single-byte kana
        before = []
        j = i - 1
        while len(before) < args.kana_before and j >= 0 and is_kana(data[j]):
            before.append(data[j])
            j -= 1
        if len(before) < args.kana_before:
            continue
        before.reverse()

        # after: kanji pairs
        k = i + 2
        kanji = []
        for _ in range(args.kanji):
            if k + 1 < len(data) and 0x88 <= data[k] <= 0x8D:
                kanji.append(kanji_index(data[k], data[k + 1]))
                k += 2
            else:
                break
        if len(kanji) < args.kanji:
            continue

        # then N single-byte kana
        kana = []
        while len(kana) < args.kana_after and k < len(data) and is_kana(data[k]):
            kana.append(data[k])
            k += 1
        if len(kana) < args.kana_after:
            continue

        if data[k : k + 4] != b"\x81\x63\x81\x63":
            continue

        hits += 1
        print(f"== 0x{i:x}")
        print(f"   kana before 、 : {[f'{b:02x}' for b in before]}")
        print(f"   kanji          : glyph indices {kanji}")
        print(f"   kana after     : {[f'{b:02x}' for b in kana]}")
        raw = data[i - 8 : k + 6]
        print("   raw            : " + " ".join(f"{b:02x}" for b in raw))
    if hits == 0:
        print("no match")


if __name__ == "__main__":
    main()

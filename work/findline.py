"""Locate speaker-name blocks 【...】 in the script and dump the bytes around them.

0x8179/0x817A are genuine Shift-JIS 【 】 and wrap the speaker name, so they give a
reliable anchor for reading the surrounding dialogue encoding.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from decode_script import kanji_index

STREAM = Path(r"D:\psp\원격수사\font_extract\script_stream.bin")
OPEN = bytes([0x81, 0x79])
CLOSE = bytes([0x81, 0x7A])


def dump(data: bytes, start: int, length: int) -> None:
    for offset in range(start, start + length, 24):
        chunk = data[offset : offset + 24]
        hexpart = " ".join(f"{b:02x}" for b in chunk)
        print(f"   {offset:08x}  {hexpart}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--before", type=int, default=24)
    parser.add_argument("--after", type=int, default=120)
    parser.add_argument("--names", action="store_true", help="histogram the names instead")
    args = parser.parse_args()

    data = STREAM.read_bytes()

    if args.names:
        names = Counter()
        pos = 0
        while True:
            a = data.find(OPEN, pos)
            if a < 0:
                break
            b = data.find(CLOSE, a, a + 32)
            if b > 0:
                names[data[a + 2 : b]] += 1
            pos = a + 2
        print(f"{sum(names.values())} name blocks, {len(names)} distinct")
        for raw, count in names.most_common(20):
            codes = " ".join(f"{c:02x}" for c in raw)
            glyphs = []
            for i in range(0, len(raw) - 1, 2):
                if 0x88 <= raw[i] <= 0x8D:
                    glyphs.append(kanji_index(raw[i], raw[i + 1]))
            print(f"   {count:5d}  [{codes}]  glyph indices {glyphs}")
        return

    shown = 0
    pos = 0
    while shown < args.count:
        a = data.find(OPEN, pos)
        if a < 0:
            break
        pos = a + 2
        if a < 0x3AC80:
            continue
        print(f"== 【 at 0x{a:x}")
        dump(data, a - args.before, args.before + args.after)
        print()
        shown += 1


if __name__ == "__main__":
    main()

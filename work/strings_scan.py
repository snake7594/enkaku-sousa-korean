"""Pull ASCII strings out of a binary and highlight font / text related hits."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

KEYWORDS = [
    "font", "Font", "FONT", "glyph", "Glyph", "GLYPH", "pgf", "PGF",
    "sceFont", "sceLibFont", "moji", "MOJI", "text", "Text", "TEXT",
    "msg", "Msg", "MSG", "char", "Char", "sjis", "SJIS", "Shift", "utf",
    "UTF", "kanji", "kana", "ruby", "フォント",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--min", type=int, default=5)
    parser.add_argument("--filter", action="store_true", help="only keyword hits")
    args = parser.parse_args()

    data = args.path.read_bytes()
    pattern = re.compile(rb"[\x20-\x7e]{%d,}" % args.min)
    seen = set()
    for match in pattern.finditer(data):
        s = match.group().decode("ascii")
        if args.filter and not any(k in s for k in KEYWORDS):
            continue
        if s in seen:
            continue
        seen.add(s)
        print(f"0x{match.start():08x}  {s}")


if __name__ == "__main__":
    main()

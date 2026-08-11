"""Replace runs of ASCII periods with the ellipsis glyph the font already draws.

The script's own convention is U+2026, which the encoder passes through as 0x81 0x63 -- two
bytes for the whole ellipsis.  Three ASCII periods cost six, so every occurrence is four
bytes wider than it needs to be, and the line runs past the edge of the dialogue box.

Runs are folded three at a time so `......` becomes `……`, matching how the Japanese writes
it.  A trailing one or two periods are left alone: turning `..` into `…` would change the
punctuation rather than fix its encoding.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")
RUN = re.compile(r"\.{3,}")


def fold(match: re.Match) -> str:
    dots = len(match.group())
    return "\u2026" * (dots // 3) + "." * (dots % 3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tsv", type=Path,
                        default=ROOT / "build" / "translation_ko_runtime_final.tsv")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "build" / "translation_ko_ellipsis.tsv")
    args = parser.parse_args()

    header, rows = translation_text.parse_loose_tsv(args.tsv)
    changed = folded = 0
    out = []
    for row in rows:
        if len(row) >= 3 and RUN.search(row[2]):
            folded += len(RUN.findall(row[2]))
            row = [row[0], row[1], RUN.sub(fold, row[2])]
            changed += 1
        out.append(row)

    args.out.write_text(header + "\n" + "\n".join("\t".join(r) for r in out) + "\n",
                        encoding="utf-8")
    print(f"{changed} rows, {folded} runs folded -> {args.out}")

    # every folded run saves four bytes per three periods
    saved = sum(len(m.group()) // 3 * 4
                for r in rows if len(r) >= 3 for m in RUN.finditer(r[2]))
    print(f"about {saved} bytes recovered from the dialogue budget")


if __name__ == "__main__":
    main()

"""Find glyph slots the script never references.

The font has 1368 glyphs but the script does not use all of them, so the spare slots
can hold Hangul for a test without disturbing a single existing line.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

RAW = Path(r"D:\psp\원격수사\font_extract\script_full_raw.tsv")
TOTAL_GLYPHS = 1368


def used_counts() -> Counter:
    return Counter(int(m) for m in re.findall(r"\[(\d+)\]", RAW.read_text(encoding="utf-8")))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-uses", type=int, default=0,
                        help="also list slots used at most this many times")
    args = parser.parse_args()

    uses = used_counts()
    free = [i for i in range(TOTAL_GLYPHS) if uses.get(i, 0) <= args.max_uses]
    print(f"{TOTAL_GLYPHS} glyphs, {len(uses)} referenced, {len(free)} with <= {args.max_uses} uses")
    print("free slots:", free)

    # slots that pair up inside one 32x16 tile are the most convenient to overwrite
    pairs = [(i, i + 1) for i in free if i % 2 == 0 and (i + 1) in free]
    print(f"\n{len(pairs)} of them form whole tiles: {pairs[:20]}")


if __name__ == "__main__":
    main()

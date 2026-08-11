"""Check whether glyph indices were assigned in order of first use in the script.

If they were, the font was produced by a subsetting tool that walked the script and
handed out the next free index to each new character — which means the game itself
never needs a code->character table, and none will be found in the data.
"""

from __future__ import annotations

import argparse

import ruby
from decode_script import (KANJI_HI, KANJI_LO, LEAD_HI, LEAD_LO, STREAM,
                           kanji_index, text_spans)


def kanji_stream(span: bytes) -> list[int]:
    out = []
    i = 0
    n = len(span)
    while i < n:
        b = span[i]
        if b == 0x0F:
            i += 2 if (i + 1 < n and 0x31 <= span[i + 1] <= 0x39) else 1
        elif b < 0x20:
            i += 2 if b == 0x16 else 1
        elif LEAD_LO <= b <= LEAD_HI and i + 1 < n:
            if KANJI_LO <= b <= KANJI_HI:
                out.append(kanji_index(b, span[i + 1]))
            i += 2
        else:
            i += 1
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=60)
    args = parser.parse_args()

    spans = text_spans(STREAM.read_bytes())
    first_seen: list[int] = []
    seen = set()
    for _, span in spans:
        for glyph in kanji_stream(span):
            if glyph not in seen:
                seen.add(glyph)
                first_seen.append(glyph)

    print(f"{len(first_seen)} distinct kanji glyphs, in order of first appearance")
    print("first 40:", first_seen[:40])

    ascending = sum(1 for a, b in zip(first_seen, first_seen[1:]) if b > a)
    print(f"pairs where the next new glyph has a higher index: "
          f"{ascending}/{len(first_seen) - 1} ({ascending * 100 / max(1, len(first_seen) - 1):.1f}%)")

    # how close is the first-use order to the identity permutation?
    offsets = [abs(pos - glyph) for pos, glyph in enumerate(first_seen)]
    print(f"mean |position - index| = {sum(offsets) / len(offsets):.1f}")


if __name__ == "__main__":
    main()

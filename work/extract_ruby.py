"""Extract (kanji glyphs, furigana reading) pairs from the script.

0x0F is a standalone delimiter: <base kanji> 0F <reading kana> 0F <rest>.
Verified against 「[69][70] 0F かんろく 0F があるわ」 = 「貫禄があるわ」.

Each pair pins down the reading of a specific glyph sequence, which is far stronger
evidence than bitmap similarity alone.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from decode_script import HIRA, HIRA_BASE, HALFWIDTH, KANJI_LO, KANJI_HI, LEAD_LO, LEAD_HI
from decode_script import STREAM, kanji_index, text_spans

RUBY = 0x0F


def kana_of(b: int) -> str | None:
    if HIRA_BASE <= b < HIRA_BASE + len(HIRA):
        return HIRA[b - HIRA_BASE]
    if 0xA1 <= b <= 0xDF:
        return HALFWIDTH[b - 0xA1]
    return None


def parse(span: bytes) -> list[tuple[tuple[int, ...], str]]:
    """Return (glyph indices of the base, reading) for each ruby run in the span."""
    tokens: list[tuple[str, object]] = []
    i = 0
    n = len(span)
    while i < n:
        b = span[i]
        if b == RUBY:
            tokens.append(("ruby", None))
            i += 1
        elif b < 0x20:
            tokens.append(("ctrl", b))
            i += 1 + (1 if b == 0x16 else 0)
        elif LEAD_LO <= b <= LEAD_HI and i + 1 < n:
            if KANJI_LO <= b <= KANJI_HI:
                tokens.append(("kanji", kanji_index(b, span[i + 1])))
            else:
                tokens.append(("punct", (b, span[i + 1])))
            i += 2
        else:
            kana = kana_of(b)
            tokens.append(("kana", kana) if kana else ("other", b))
            i += 1

    pairs = []
    j = 0
    while j < len(tokens):
        if tokens[j][0] != "ruby":
            j += 1
            continue
        # reading runs until the closing delimiter
        k = j + 1
        reading = []
        while k < len(tokens) and tokens[k][0] == "kana":
            reading.append(tokens[k][1])
            k += 1
        if k >= len(tokens) or tokens[k][0] != "ruby" or not reading:
            j += 1
            continue
        # base is the kanji run immediately before the opening delimiter
        base = []
        m = j - 1
        while m >= 0 and tokens[m][0] == "kanji":
            base.append(tokens[m][1])
            m -= 1
        base.reverse()
        if base:
            pairs.append((tuple(base), "".join(reading)))
        j = k + 1
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    data = STREAM.read_bytes()
    spans = text_spans(data)
    counts = Counter()
    for _, span in spans:
        for base, reading in parse(span):
            counts[(base, reading)] += 1

    glyphs = {g for base, _ in counts for g in base}
    print(f"{sum(counts.values())} ruby instances, {len(counts)} distinct pairs, "
          f"covering {len(glyphs)} distinct glyphs")

    print(f"\ntop {args.top} pairs:")
    for (base, reading), count in counts.most_common(args.top):
        ids = "".join(f"[{g}]" for g in base)
        print(f"   {count:5d}  {ids:<20s} {reading}")

    single = Counter()
    for (base, reading), count in counts.items():
        if len(base) == 1:
            single[(base[0], reading)] += count
    print(f"\n{len(single)} single-glyph ruby pairs (strongest evidence):")
    for (glyph, reading), count in single.most_common(30):
        print(f"   {count:5d}  [{glyph}] = {reading}")

    if args.out:
        payload = [{"base": list(base), "reading": reading, "count": count}
                   for (base, reading), count in counts.most_common()]
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

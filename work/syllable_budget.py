"""Count how many distinct Hangul syllables the translation needs against the font's capacity.

The compression measurement came back meaningless -- 7,828 of 7,841 rows would not encode --
because the encoder can only emit syllables that already have a glyph, and the font was
only ever filled with a test set.  So the real constraint is not compression at all: it is
how many distinct syllables the script uses versus how many glyph slots exist.

The font holds 684 tiles of two 16x16 glyphs each, so 1,368 slots, and every one currently
holds a kanji.  If the script needs more syllables than that, no amount of reflow helps and
the font itself has to change shape.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

TSV = Path(r"D:\psp\원격수사\build\translation_ko.tsv")
SLOTS = Path(r"D:\psp\원격수사\build\korean_slots.json")
CAPACITY = 684 * 2


def main() -> None:
    rows = TSV.read_text(encoding="utf-8").splitlines()[1:]
    texts = [line.split("\t")[2] for line in rows if len(line.split("\t")) > 2]
    joined = "".join(texts).replace("\\n", "")

    syllables = Counter(c for c in joined if 0xAC00 <= ord(c) <= 0xD7A3)
    other = Counter(c for c in joined if not (0xAC00 <= ord(c) <= 0xD7A3))
    print(f"translation: {len(rows)} rows, {len(joined)} characters")
    print(f"   {len(syllables)} distinct Hangul syllables, "
          f"{sum(syllables.values())} occurrences")
    print(f"   {len(other)} distinct non-Hangul characters")
    print(f"      {''.join(sorted(other))[:100]}")

    slots = json.loads(SLOTS.read_text(encoding="utf-8"))
    covered = set(slots) & set(syllables)
    print(f"\nkorean_slots.json: {len(slots)} entries, "
          f"{len(covered)} of them are syllables this script uses")

    print(f"\nfont capacity: {CAPACITY} glyph slots (684 tiles x 2)")
    need = len(syllables) + len(other)
    print(f"   script needs {need} glyphs; "
          f"{'fits with ' + str(CAPACITY - need) + ' to spare' if need <= CAPACITY else 'OVER by ' + str(need - CAPACITY)}")

    # how much of the text would a smaller font still cover?
    total = sum(syllables.values())
    running = 0
    for limit in (500, 800, 1000, 1200, 1368):
        running = sum(n for _, n in syllables.most_common(limit))
        print(f"   the {limit} most common syllables cover "
              f"{100.0 * running / total:.2f}% of all syllable occurrences")

    rare = [(c, n) for c, n in syllables.items() if n <= 2]
    print(f"\n{len(rare)} syllables appear at most twice "
          f"({sum(n for _, n in rare)} occurrences total)")


if __name__ == "__main__":
    main()

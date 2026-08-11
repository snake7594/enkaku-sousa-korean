"""List the furigana readings attached to glyphs the resolver could not decide.

Personal names and place names carry ruby in the script but are absent from a kanji
dictionary, so the earlier pass discarded exactly the evidence that identifies them.
Pairing each unresolved glyph with the readings it actually appears with turns those
back into something usable.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import ruby

RAW = Path(r"D:\psp\원격수사\font_extract\script_full_raw.tsv")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--charmap", type=Path, required=True)
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args()

    table = json.loads(args.charmap.read_text(encoding="utf-8"))
    unresolved = {e["index"] for e in table if e["source"] == "bitmap"}
    guess = {e["index"]: e["char"] for e in table}
    alts = {e["index"]: e.get("alts", []) for e in table}

    uses = Counter(int(m) for m in re.findall(r"\[(\d+)\]", RAW.read_text(encoding="utf-8")))

    counts = ruby.all_pairs()
    by_glyph: dict[int, list[tuple[tuple[int, ...], str, int]]] = defaultdict(list)
    for (base, reading), count in counts.items():
        for glyph in base:
            if glyph in unresolved:
                by_glyph[glyph].append((base, reading, count))

    covered = [g for g in unresolved if g in by_glyph]
    print(f"{len(unresolved)} unresolved glyphs, {len(covered)} of them carry ruby readings\n")

    ranked = sorted(covered, key=lambda g: -uses.get(g, 0))
    for glyph in ranked[: args.top]:
        entries = sorted(by_glyph[glyph], key=lambda e: -e[2])[:3]
        shown = "; ".join(
            f"{''.join(f'[{b}]' for b in base)}={reading}({count}x)" for base, reading, count in entries
        )
        print(f"glyph {glyph:4d}  used {uses.get(glyph, 0):4d}x  guess {guess[glyph]}  "
              f"alts {' '.join(alts[glyph][:4])}")
        print(f"           ruby: {shown}")

    print(f"\n{len(unresolved) - len(covered)} unresolved glyphs have no ruby at all")


if __name__ == "__main__":
    main()

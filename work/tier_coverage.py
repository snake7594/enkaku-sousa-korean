"""Report the table by confidence tier, weighted by how often each glyph is used.

Counting glyphs alone understates the practical picture: the glyphs still unresolved
are mostly rare ones, so what matters to a translator is what share of the kanji
*occurrences* in the script fall in each tier.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

RAW = Path(r"D:\psp\원격수사\font_extract\script_full_raw.tsv")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--charmap", type=Path, required=True)
    parser.add_argument("--top-unresolved", type=int, default=15)
    args = parser.parse_args()

    table = json.loads(args.charmap.read_text(encoding="utf-8"))
    tier = {e["index"]: (e["source"], e["confidence"]) for e in table}

    text = RAW.read_text(encoding="utf-8")
    uses = Counter(int(m) for m in re.findall(r"\[(\d+)\]", text))
    total_uses = sum(uses.values())

    by_tier_glyphs = Counter(tier.values())
    by_tier_uses = Counter()
    for glyph, count in uses.items():
        if glyph in tier:
            by_tier_uses[tier[glyph]] += count

    print(f"{len(table)} glyphs, {total_uses} kanji occurrences in the script\n")
    print(f"{'source':10s} {'conf':8s} {'glyphs':>7s} {'occurrences':>12s} {'share':>7s}")
    for key in sorted(by_tier_glyphs, key=lambda k: -by_tier_uses[k]):
        source, conf = key
        n_uses = by_tier_uses[key]
        print(f"{source:10s} {conf:8s} {by_tier_glyphs[key]:7d} {n_uses:12d} "
              f"{n_uses * 100 / total_uses:6.1f}%")

    trusted = sum(n for k, n in by_tier_uses.items() if k[0] != "bitmap")
    print(f"\noccurrences covered by non-bitmap evidence: {trusted}/{total_uses} "
          f"({trusted * 100 / total_uses:.1f}%)")

    print(f"\nmost-used glyphs still bitmap-only (worth checking by eye first):")
    low = [(count, glyph) for glyph, count in uses.items()
           if tier.get(glyph, ("bitmap",))[0] == "bitmap"]
    low.sort(reverse=True)
    guess = {e["index"]: e["char"] for e in table}
    for count, glyph in low[: args.top_unresolved]:
        alts = next((e.get("alts", []) for e in table if e["index"] == glyph), [])
        print(f"   glyph {glyph:4d}  used {count:4d}x  guess {guess.get(glyph)}  "
              f"alts {' '.join(alts[:5])}")


if __name__ == "__main__":
    main()

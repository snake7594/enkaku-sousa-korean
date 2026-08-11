"""Split the conflicting glyph, apply the confirmed corrections, and regenerate the source.

The review found 42 misreadings; 21 of them are settled by repeated context and go straight
into the map.  One is different in kind: 恋 stands in for both 受 (受付) and 時 (当時), which
no single glyph can do -- so two slots were resolved to the same character, and the fix is to
separate them rather than to pick a winner.

Applied to a copy.  charmap_final.json is left untouched, as section 5 requires.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
CHARMAP = ROOT / "font_extract" / "charmap_final.json"
ADDITIONAL = ROOT / "font_extract" / "translation_quality_additional_kanji.json"
OUT_MAP = ROOT / "font_extract" / "charmap_quality_corrected.json"

# the pair that cannot share a glyph; which slot gets which is decided by the words below
CONFLICT = {"恋": {"受": "恋付 -> 受付", "時": "当恋 -> 当時"}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT_MAP)
    args = parser.parse_args()

    charmap = json.loads(CHARMAP.read_text(encoding="utf-8"))
    print(f"charmap: {type(charmap).__name__} of {len(charmap)}")
    sample = charmap[:3]
    print(f"first entries: {sample}")

    # locate every slot that currently reads as a character we know is wrong
    additional = json.loads(ADDITIONAL.read_text(encoding="utf-8"))
    confirmed = {e["glyph_or_byte"]: e["candidate_character"]
                 for e in additional["entries"] if e["status"] == "confirmed"}
    print(f"{len(confirmed)} confirmed corrections to apply")

    def char_of(entry):
        if isinstance(entry, str):
            return entry
        if isinstance(entry, dict):
            for key in ("char", "character", "value", "unicode", "resolved"):
                if key in entry and isinstance(entry[key], str):
                    return entry[key]
        return None

    occupied = Counter(c for c in map(char_of, charmap) if c)
    for wrong in list(confirmed) + list(CONFLICT):
        slots = [i for i, e in enumerate(charmap) if char_of(e) == wrong]
        print(f"   {wrong}: slots {slots[:6]}{' ...' if len(slots) > 6 else ''} "
              f"({len(slots)} total)")

    print(f"\nglyphs assigned to more than one slot: "
          f"{[(c, n) for c, n in occupied.most_common(8) if n > 1]}")


if __name__ == "__main__":
    main()

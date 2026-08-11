"""Test whether the translation changes the number of lines each dialogue box holds.

Everything else has been ruled out by experiment: references remap correctly, the archive
carries no offset table, nothing outside the stream addresses the text, size alone is not it
(shrinking fails too), and there is no length field beside a line.  What has not been checked
is the line *count*.

The TSV keeps it in its own column, which means something upstream cared about it.  Korean
runs about 140% of Japanese, so a line that fitted in two rows now needs three, and the count
changes even when the byte length is preserved.  If the engine reserves or advances by that
count, a changed one desyncs it -- which matches every observation, including that shrinking
breaks the game just as reliably as growing it.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import encode_korean
import translation_text

ROOT = Path(r"D:\psp\원격수사")
JA = ROOT / "font_extract" / "script_full_ja.tsv"
KO = ROOT / "build" / "translation_ko_clean.tsv"


def rows(path: Path):
    _, data = translation_text.parse_loose_tsv(path)
    return {r[0].strip().lower(): (r[1], r[2]) for r in data if len(r) >= 3}


def main() -> None:
    ja, ko = rows(JA), rows(KO)
    keys = [k for k in ja if k in ko]

    same, differ = 0, Counter()
    declared_mismatch = 0
    for key in keys:
        ja_lines = ja[key][1].count("\\n") + 1
        ko_lines = ko[key][1].count("\\n") + 1
        if ja_lines == ko_lines:
            same += 1
        else:
            differ[ko_lines - ja_lines] += 1
        declared = ja[key][0]
        if declared.isdigit() and int(declared) != ja_lines:
            declared_mismatch += 1

    total = len(keys)
    print(f"{total} rows")
    print(f"   line count unchanged: {same} ({100.0 * same / total:.1f}%)")
    print(f"   changed:              {total - same} "
          f"({100.0 * (total - same) / total:.1f}%)")
    print(f"   by how much: {dict(sorted(differ.items())[:8])}")
    print(f"\n   the TSV's declared count disagrees with the Japanese text in "
          f"{declared_mismatch} rows")

    # if the engine cared about the count, STEP1's rows would be the ones that kept it
    slots = {c: int(i) for c, i in json.loads(
        (ROOT / "build" / "korean_slots_full_clean.json").read_text(encoding="utf-8")
    )["slots"].items()}
    fitted_same, fitted_diff = 0, 0
    for key in keys:
        data = encode_korean.encode_text(ko[key][1].replace("\\n", "\n"), slots)
        if data is None:
            continue
        # STEP1 replaced only lines whose encoding fitted the original span
        if len(data) <= len(ja[key][1].encode("utf-8")):
            if ja[key][1].count("\\n") == ko[key][1].count("\\n"):
                fitted_same += 1
            else:
                fitted_diff += 1
    print(f"\n   among rows short enough for the in-place build: "
          f"{fitted_same} keep the line count, {fitted_diff} change it")
    print("   if the working build contains rows that changed the count, the count is "
          "not what breaks the game")


if __name__ == "__main__":
    main()

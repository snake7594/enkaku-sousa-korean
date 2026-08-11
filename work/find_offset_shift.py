"""Find where the Korean rows are shifted against the Japanese.

Around 0x000e5725 the Korean at each offset is the translation of the *next* Japanese row:
the line 「いつかオレの無実を証明してくれる…」 sits one row above its Korean.  In game that
puts every line under the wrong speaker, so it matters more than any wording.

Speaker tags find it cheaply.  Most rows open with 【name】 on both sides, and the Japanese
name maps to one Korean name by majority vote across the whole script.  A row where the
Korean tag disagrees with its own Japanese but agrees with the next Japanese row is shifted,
and consecutive such rows make the run.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")
TAG = re.compile(r"^【([^】]+)】")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ja", type=Path,
                        default=ROOT / "font_extract" / "script_full_ja_v5.tsv")
    parser.add_argument("--ko", type=Path,
                        default=ROOT / "build" / "translation_ko_v2_kayo.tsv")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "offset_shift.json")
    args = parser.parse_args()

    _, ja_rows = translation_text.parse_loose_tsv(args.ja)
    _, ko_rows = translation_text.parse_loose_tsv(args.ko)
    ja = [r for r in ja_rows if len(r) >= 3]
    ko = [r for r in ko_rows if len(r) >= 3]
    if [r[0] for r in ja] != [r[0] for r in ko]:
        raise SystemExit("the two files do not carry the same offsets")

    ja_tag = [TAG.match(r[2]).group(1) if TAG.match(r[2]) else None for r in ja]
    ko_tag = [TAG.match(r[2]).group(1) if TAG.match(r[2]) else None for r in ko]

    votes = defaultdict(Counter)
    for a, b in zip(ja_tag, ko_tag):
        if a and b:
            votes[a][b] += 1
    canon = {a: c.most_common(1)[0][0] for a, c in votes.items()}

    aligned, shifted = [], []
    for i, (a, b) in enumerate(zip(ja_tag, ko_tag)):
        if not a or not b:
            aligned.append(None)
            shifted.append(None)
            continue
        aligned.append(canon.get(a) == b)
        nxt = ja_tag[i + 1] if i + 1 < len(ja_tag) else None
        shifted.append(bool(nxt) and canon.get(nxt) == b)

    runs, start = [], None
    for i in range(len(ja)):
        bad = aligned[i] is False and shifted[i] is True
        if bad and start is None:
            start = i
        elif not bad and start is not None:
            if i - start >= 3:
                runs.append((start, i - 1))
            start = None
    if start is not None and len(ja) - start >= 3:
        runs.append((start, len(ja) - 1))

    total = sum(hi - lo + 1 for lo, hi in runs)
    report = [{"from": ja[lo][0], "to": ja[hi][0], "rows": hi - lo + 1,
               "first_ja": ja[lo][2][:60], "first_ko": ko[lo][2][:60]}
              for lo, hi in runs]
    args.out.write_text(json.dumps(
        {"schema": "enkaku_offset_shift_v1",
         "rows_checked": sum(1 for x in aligned if x is not None),
         "rows_mismatched": sum(1 for x in aligned if x is False),
         "runs": len(runs), "rows_in_runs": total, "detail": report},
        ensure_ascii=False, indent=1), encoding="utf-8")

    checked = sum(1 for x in aligned if x is not None)
    print(f"{checked} rows carry a tag on both sides, "
          f"{sum(1 for x in aligned if x is False)} disagree")
    print(f"{len(runs)} runs of 3+ rows look shifted by one, {total} rows total\n")
    for r in report[:12]:
        print(f"   {r['from']} .. {r['to']}  {r['rows']:4d} rows")
        print(f"      JA {r['first_ja']}")
        print(f"      KO {r['first_ko']}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

"""Measure what the 175 recovered glyphs mean for the Korean already written.

2712 rows of the Japanese change, but a changed row is not automatically a damaged
translation: some of those characters sat in a word the translator could read around.  What
does real damage is a recurring term that was nonsense in the old source, because the
translator had to invent something and then reuse the invention.

So this ranks the changes by what actually reaches the player.  It pulls the words that
changed, counts how often each recurs, and shows what the current Korean says for it.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")
CJK = re.compile(r"[\u4e00-\u9fff]")


def words_around(before: str, after: str):
    """The kanji runs that differ, with a little context, as (old, new) pairs."""
    out = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, before, after).get_opcodes():
        if tag != "replace":
            continue
        lo, hi = i1, i2
        while lo > 0 and CJK.match(before[lo - 1]):
            lo -= 1
        while hi < len(before) and CJK.match(before[hi]):
            hi += 1
        out.append((before[lo:hi], after[lo - i1 + j1:hi - i2 + j2] if hi - i2 >= 0 else after[j1:j2]))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "ja_v4_report.json")
    parser.add_argument("--tsv", type=Path,
                        default=ROOT / "build" / "translation_ko_v2_kayo.tsv")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "v4_impact.json")
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()

    data = json.loads(args.report.read_text(encoding="utf-8"))
    _, rows = translation_text.parse_loose_tsv(args.tsv)
    ko = {r[0].strip().lower(): r[2] for r in rows if len(r) >= 3}

    counts = Counter()
    where = defaultdict(list)
    for change in data["changes"]:
        for old, new in words_around(change["before"], change["after"]):
            if not CJK.search(new):
                continue
            counts[(old, new)] += 1
            where[(old, new)].append(change["offset"])

    ranked = []
    for (old, new), n in counts.most_common():
        samples = []
        for offset in where[(old, new)][:2]:
            text = ko.get(offset.strip().lower(), "")
            samples.append({"offset": offset, "ko": text[:90]})
        ranked.append({"old": old, "new": new, "rows": n, "samples": samples})

    args.out.write_text(json.dumps({"schema": "enkaku_v4_impact_v1",
                                    "changed_rows": data["changed_rows"],
                                    "distinct_words": len(ranked), "words": ranked},
                                   ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{data['changed_rows']} rows change, {len(ranked)} distinct words\n")
    for row in ranked[: args.top]:
        print(f"{row['rows']:4d}x  {row['old']}  ->  {row['new']}")
        for s in row["samples"][:1]:
            print(f"        ko: {s['ko']}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

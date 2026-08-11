"""Replace the 아야 artefact with the pronoun the Japanese actually uses.

彼 and 彼女 came through as 아야 and 아야녀, which read as a person's name that does not
exist in the game -- 「아야가 했다고 자백한 이상」 for 「彼がやったと自白している以上」.

Conditioned on the source: a row is only touched when its Japanese contains 彼女 or 彼, and
which one decides the replacement.  A global search-and-replace would also hit any line
where 아야 is genuinely part of a word, which is what the review document forbids.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")
JA = ROOT / "font_extract" / "script_full_ja_corrected.tsv"

# longest first, so 아야녀 is handled before 아야
FEMALE = [("아야녀", "그녀"), ("아야메", "그녀"), ("아야", "그녀")]
MALE = [("아야녀", "그"), ("아야등", "그들"), ("아야", "그")]


def rows(path: Path):
    header, data = translation_text.parse_loose_tsv(path)
    return header, data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tsv", type=Path,
                        default=ROOT / "build" / "translation_ko_ellipsis.tsv")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "build" / "translation_ko_pronoun.tsv")
    parser.add_argument("--report", type=Path,
                        default=ROOT / "build" / "pronoun_fix_report.json")
    args = parser.parse_args()

    _, ja_rows = rows(JA)
    ja = {r[0].strip().lower(): r[2] for r in ja_rows if len(r) >= 3}
    header, ko_rows = rows(args.tsv)

    changed, skipped, out = [], [], []
    for row in ko_rows:
        if len(row) < 3 or "아야" not in row[2]:
            out.append(row)
            continue
        key = row[0].strip().lower()
        source = ja.get(key, "")
        if "彼女" in source:
            table = FEMALE
        elif "彼" in source:
            table = MALE
        else:
            # 아야 without 彼 in the source is either a real word or a different fault;
            # either way it is not this fix's business
            skipped.append({"index": key, "ja": source[:60], "ko": row[2][:60]})
            out.append(row)
            continue
        text = row[2]
        for bad, good in table:
            text = text.replace(bad, good)
        changed.append({"index": key, "before": row[2][:70], "after": text[:70],
                        "source_has": "彼女" if table is FEMALE else "彼"})
        out.append([row[0], row[1], text])

    args.out.write_text(header + "\n" + "\n".join("\t".join(r) for r in out) + "\n",
                        encoding="utf-8")
    args.report.write_text(json.dumps(
        {"schema": "enkaku_pronoun_fix_v1", "changed": len(changed),
         "skipped_no_source_pronoun": len(skipped),
         "changes": changed, "skipped": skipped[:40]},
        ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(changed)} rows fixed, {len(skipped)} left alone "
          f"(no 彼/彼女 in the source)")
    kinds = Counter(c["source_has"] for c in changed)
    print(f"   {dict(kinds)}")
    for c in changed[:5]:
        print(f"\n   {c['index']} ({c['source_has']})")
        print(f"     - {c['before']}")
        print(f"     + {c['after']}")
    print(f"\n-> {args.out}\n-> {args.report}")


if __name__ == "__main__":
    main()

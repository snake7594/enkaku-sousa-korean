"""Find Japanese proper nouns the Korean renders more than one way.

The earlier correspondence check asked whether a row named someone the other side did not.
That catches a line handed to the wrong character, but it is blind to a name spelled two ways,
because both spellings are present and neither looks invented.  桜蔭高校 slipped through as
준텐 고등학교 in one row and 오인 고등학교 in another, and 神崎茜 as 리키자키 아카네 next to
간자키 아카네.

So this asks a different question: gather every row containing a given Japanese term, pull the
Korean that sits where the name should be, and report any term with more than one answer.  The
terms come from the script itself -- runs of kanji and katakana that recur -- rather than from
a list I write, so it finds names nobody thought to check.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")

TERM = re.compile(r"[\u4e00-\u9fff]{2,6}(?:[\u30a0-\u30ff]{2,8})?|[\u30a0-\u30ff]{3,10}")
HANGUL = re.compile(r"[가-힣]+")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ja", type=Path,
                        default=ROOT / "font_extract" / "script_full_ja_v5.tsv")
    parser.add_argument("--ko", type=Path, default=ROOT / "build" / "translation_ko_v5.tsv")
    parser.add_argument("--min-rows", type=int, default=4)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "term_check.json")
    args = parser.parse_args()

    _, ja_rows = translation_text.parse_loose_tsv(args.ja)
    _, ko_rows = translation_text.parse_loose_tsv(args.ko)
    ja = [r for r in ja_rows if len(r) >= 3]
    ko = [r for r in ko_rows if len(r) >= 3]

    # a term is interesting when it recurs; a name does, a stray compound does not
    counts = Counter()
    for row in ja:
        counts.update(set(TERM.findall(row[2])))
    terms = [t for t, n in counts.items() if n >= args.min_rows]

    # for each term, what Hangul words show up in its rows but rarely elsewhere
    where = defaultdict(list)
    for i, row in enumerate(ja):
        for term in TERM.findall(row[2]):
            if counts[term] >= args.min_rows:
                where[term].append(i)

    background = Counter()
    for row in ko:
        background.update(set(HANGUL.findall(row[2])))
    total = len(ko)

    suspicious = []
    for term in terms:
        rows = where[term]
        local = Counter()
        for i in set(rows):
            local.update(set(HANGUL.findall(ko[i][2])))
        # words that appear in most of the term's rows but are rare overall are its rendering
        candidates = []
        for word, n in local.items():
            if len(word) < 2 or n < max(2, len(set(rows)) * 0.25):
                continue
            lift = (n / len(set(rows))) / max(1e-9, background[word] / total)
            if lift > 8:
                candidates.append((round(lift, 1), n, word))
        candidates.sort(reverse=True)
        if len(candidates) > 1 and candidates[0][2] != candidates[1][2]:
            top = candidates[:4]
            suspicious.append({"term": term, "rows": len(set(rows)),
                               "renderings": [{"word": w, "rows": n, "lift": l}
                                              for l, n, w in top]})

    suspicious.sort(key=lambda s: -s["rows"])
    args.out.write_text(json.dumps({"schema": "enkaku_term_check_v1",
                                    "terms_examined": len(terms),
                                    "suspicious": suspicious}, ensure_ascii=False, indent=1),
                        encoding="utf-8")

    print(f"{len(terms)} recurring Japanese terms examined, "
          f"{len(suspicious)} render more than one way\n")
    for s in suspicious[:24]:
        forms = "  ".join(f"{r['word']}({r['rows']})" for r in s["renderings"])
        print(f"   {s['term']:14s} {s['rows']:4d} rows   {forms}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

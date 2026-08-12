"""Check that each proper noun is spelled one way, by looking at the rows that carry it.

A general term sweep drowns in Korean particles -- 알리바이를 and 알리바이가 are the same word
-- and in words that merely keep company with the term.  Proper nouns are different: a name is
transliterated, so the syllables are fixed, and a second spelling is a mistake rather than a
choice.

桜蔭高校 came out 준텐 고등학교 in two rows and 오인 고등학교 elsewhere, and 神崎茜 came out
리키자키 아카네 once.  Both were invisible to the correspondence check, which only flags a row
that names somebody the Japanese never mentions -- here the given name matched and the surname
did not.  So this asks the narrower question directly, for every name the plates and the script
establish.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")

# Japanese term -> the Korean it should be, from the name plates and the game's own ruby
NOUNS = {
    "桜蔭": "오인", "神崎": "간자키", "水無月": "미나즈키", "白川": "시라카와",
    "斉藤": "사이토", "水谷": "미즈타니", "沼崎": "누마사키", "七芝": "나나시바",
    "新城": "신조", "近藤": "콘도", "吉本": "요시모토", "三浦": "미우라",
    "樋口": "히구치", "中川": "나카가와", "西島": "니시지마", "田代": "다시로",
    "朝露": "아사츠유", "佳代": "가요", "一朗": "이치로", "志朗": "시로",
    "真二": "신지", "美佐恵": "미사에", "安代": "야스요", "克美": "가쓰미",
    "栄太郎": "에이타로", "晋太郎": "신타로", "澄香": "스미카", "伊月": "이즈키",
    "清香": "사야카", "正信": "마사노부", "幸司": "코우지",
}
HANGUL_WORD = re.compile(r"[가-힣]+")
PARTICLES = ("으로", "에서", "에게", "이랑", "라고", "라는", "와", "과", "을", "를", "이",
             "가", "은", "는", "의", "에", "도", "로", "만", "씨", "군", "님")


def stem(word: str) -> str:
    for p in sorted(PARTICLES, key=len, reverse=True):
        if len(word) > len(p) + 1 and word.endswith(p):
            return word[: -len(p)]
    return word


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ja", type=Path,
                        default=ROOT / "font_extract" / "script_full_ja_v5.tsv")
    parser.add_argument("--ko", type=Path, default=ROOT / "build" / "translation_ko_v5.tsv")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "proper_nouns.json")
    args = parser.parse_args()

    _, ja_rows = translation_text.parse_loose_tsv(args.ja)
    _, ko_rows = translation_text.parse_loose_tsv(args.ko)
    ja = [r for r in ja_rows if len(r) >= 3]
    ko = [r for r in ko_rows if len(r) >= 3]

    report, bad = [], 0
    for term, want in NOUNS.items():
        rows = [i for i, r in enumerate(ja) if term in r[2]]
        if not rows:
            continue
        with_it = sum(1 for i in rows if want in ko[i][2])
        without = [i for i in rows if want not in ko[i][2]]
        # what the rows missing the expected spelling say instead
        others = Counter()
        for i in without:
            for word in HANGUL_WORD.findall(ko[i][2]):
                s = stem(word)
                if 2 <= len(s) <= 6:
                    others[s] += 1
        entry = {"term": term, "expected": want, "rows": len(rows),
                 "rows_with_expected": with_it, "rows_without": len(without),
                 "offsets_without": [ja[i][0] for i in without[:8]],
                 "words_in_those_rows": [w for w, _ in others.most_common(6)]}
        report.append(entry)
        if without and with_it:
            bad += 1

    report.sort(key=lambda e: -e["rows_without"])
    args.out.write_text(json.dumps({"schema": "enkaku_proper_nouns_v1", "terms": report},
                                   ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(report)} proper nouns checked\n")
    print(f"{'term':10s} {'expected':10s} {'rows':>5s} {'ok':>5s} {'other':>6s}")
    for e in report:
        if not e["rows_without"]:
            continue
        print(f"{e['term']:10s} {e['expected']:10s} {e['rows']:5d} "
              f"{e['rows_with_expected']:5d} {e['rows_without']:6d}   "
              f"{e['words_in_those_rows'][:4]}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

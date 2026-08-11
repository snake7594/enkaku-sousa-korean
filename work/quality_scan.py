"""Source-conditioned scan of every Japanese/Korean pair (review doc section 4).

Nine thousand pairs cannot be read one by one, but they can all be *checked* -- and the
checks have to be conditioned on the Japanese, not run as global searches over the Korean.
That distinction is the whole point: "곰팡이" is only wrong where the source says クビ, and
a global replace would corrupt the rows where it is genuinely mould.

Two kinds of rule:

  term    the source contains a specific word whose rendering is known to have gone wrong
          before, so the Korean is required to contain one of its acceptable forms
  formal  properties that must survive any translation -- digits, negation, question form,
          speaker tags -- compared between the two sides

Every hit records the source that triggered it, so a later fix can be applied on the same
condition rather than by matching Korean text.  Nothing is rewritten here; this only builds
the candidate list that section 6 asks to be reviewed and saved.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")
JA = ROOT / "font_extract" / "script_full_ja.tsv"
KO = ROOT / "build" / "translation_ko_semantic_checked.tsv"

# source word -> (acceptable Korean renderings, category, severity)
TERMS = [
    ("クビ", ("해고", "잘리", "짤리", "목"), "term", "major"),
    ("生徒", ("학생", "생도"), "term", "major"),
    ("勾留", ("구류", "구금", "유치"), "term", "major"),
    ("自殺", ("자살", "스스로 목숨"), "term", "blocker"),
    ("殺人", ("살인",), "term", "blocker"),
    ("殺害", ("살해", "살인"), "term", "blocker"),
    ("人殺し", ("살인", "죽인", "살인자"), "term", "blocker"),
    ("真犯人", ("진범",), "term", "major"),
    ("犯人", ("범인", "진범"), "term", "major"),
    ("取調", ("취조", "신문", "조사"), "term", "major"),
    ("蟇調", ("취조", "신문", "조사"), "term", "major"),
    ("弁護士", ("변호사",), "term", "major"),
    ("被害者", ("피해자",), "term", "major"),
    ("容疑者", ("용의자", "피의자"), "term", "major"),
    ("証言", ("증언",), "term", "major"),
    ("アリバイ", ("알리바이",), "term", "major"),
    ("移植", ("이식",), "term", "minor"),
    ("裁判", ("재판",), "term", "major"),
    ("警察", ("경찰",), "term", "minor"),
    ("お兄さん", ("오빠", "형"), "name", "major"),
]

DIGITS = re.compile(r"\d+")
SPEAKER = re.compile(r"^【([^】]{1,20})】")
NEGATION_JA = re.compile(r"(ない|ません|ぬ[^ら]|なかった|ないで|ず[にの])")
# Korean negates in many shapes, and several verbs are inherently negative.  The first
# version of this list flagged 545 rows, nearly all of them correct translations -- 모르다
# for わかりません, 죄송하다 for すみません -- so the rule was measuring its own narrowness.
NEGATION_KO = re.compile(unicodedata.normalize("NFD",
    r"(않|안\s|못\s|못하|없|말고|말아|아니|모르|싫|글쎄|죄송|미안|실례|무례|그만|"
    r"뿐|밖에|커녕|지 마)"))

FULLWIDTH = {ord("０") + i: ord("0") + i for i in range(10)}


def jamo(text: str) -> str:
    """Decompose Hangul so a stem matches its inflected forms.

    Korean composes a syllable from its jamo, so `아니` is simply not a substring of
    `아닌가요` -- the second syllable is 닌, not 니.  Comparing decomposed text makes the stem
    match every ending built on it, which is what a negation test actually needs.
    """
    return unicodedata.normalize("NFD", text)


def digits_of(text: str) -> Counter:
    """Digit runs, with full-width numerals folded to ASCII.

    Without the fold, ２００９ and 2009 count as different numbers and every year, count and
    time in the script reports as a mismatch -- 459 rows on the first pass, essentially all
    of them correct.
    """
    return Counter(DIGITS.findall(text.translate(FULLWIDTH)))


def rows_of(path: Path) -> dict[str, str]:
    _, rows = translation_text.parse_loose_tsv(path)
    return {r[0].strip().lower(): r[2] for r in rows if len(r) >= 3}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        default=ROOT / "build" / "translation_quality_candidates.json")
    parser.add_argument("--show", type=int, default=4)
    args = parser.parse_args()

    ja, ko = rows_of(JA), rows_of(KO)
    keys = [k for k in ja if k in ko]
    print(f"{len(keys)} pairs")

    findings = []
    for key in keys:
        src, dst = ja[key], ko[key]
        flat_ko = dst.replace("\\n", "")

        for word, ok, category, severity in TERMS:
            if word in src and not any(o in flat_ko for o in ok):
                findings.append({"index": key, "rule": f"term:{word}",
                                 "category": category, "severity": severity,
                                 "source_ja": src, "current_ko": dst,
                                 "reason": f"source contains {word}; translation has none of "
                                           f"{'/'.join(ok)}"})

        ja_nums, ko_nums = digits_of(src), digits_of(flat_ko)
        if ja_nums and ja_nums != ko_nums:
            findings.append({"index": key, "rule": "numbers", "category": "number",
                             "severity": "major", "source_ja": src, "current_ko": dst,
                             "reason": f"digits {sorted(ja_nums.elements())} in source vs "
                                       f"{sorted(ko_nums.elements())} in translation"})

        sj, sk = SPEAKER.match(src), SPEAKER.match(flat_ko)
        if bool(sj) != bool(sk):
            findings.append({"index": key, "rule": "speaker-tag", "category": "layout",
                             "severity": "major", "source_ja": src, "current_ko": dst,
                             "reason": "speaker tag present on one side only"})

        if NEGATION_JA.search(src) and not NEGATION_KO.search(jamo(flat_ko)):
            findings.append({"index": key, "rule": "negation", "category": "semantic",
                             "severity": "major", "source_ja": src, "current_ko": dst,
                             "reason": "source is negated; translation shows no negation"})

        # gross length outliers catch wholesale omission or invention
        src_len = len(re.sub(r"[【】《》\\n\s]", "", src))
        dst_len = len(re.sub(r"[【】《》\\n\s]", "", flat_ko))
        if src_len >= 12 and (dst_len < src_len * 0.35 or dst_len > src_len * 3.0):
            findings.append({"index": key, "rule": "length", "category":
                             "omission" if dst_len < src_len else "addition",
                             "severity": "minor", "source_ja": src, "current_ko": dst,
                             "reason": f"source {src_len} chars vs translation {dst_len}"})

    by_rule = Counter(f["rule"] for f in findings)
    by_sev = Counter(f["severity"] for f in findings)
    print(f"\n{len(findings)} candidate issues over "
          f"{len({f['index'] for f in findings})} distinct rows")
    print(f"   by severity: {dict(by_sev)}")
    for rule, count in by_rule.most_common(20):
        print(f"   {rule:24s} {count}")

    args.out.write_text(json.dumps(
        {"schema": "enkaku_translation_quality_candidates_v1",
         "pairs_checked": len(keys), "candidates": findings},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {args.out}")

    for rule, _ in by_rule.most_common(6):
        sample = [f for f in findings if f["rule"] == rule][: args.show]
        print(f"\n--- {rule} ---")
        for f in sample:
            print(f"   {f['index']}  ja: {f['source_ja'][:70]}")
            print(f"   {'':10}  ko: {f['current_ko'][:70]}")


if __name__ == "__main__":
    main()

"""Where the Japanese repeats itself, the Korean has to repeat itself too.

The script stores each branch separately, so whole scenes appear twice or more with byte-identical
Japanese.  That gives a check that needs no judgement: two rows with the same Japanese must carry
the same Korean, and where they do not, at least one of them is wrong.

It also gives the repair.  The block at 6226 looked scrambled -- 【三浦】's line about the pistol
sitting where 【光志】 talks about 朝露's fiance -- but the Japanese there is a second copy of the
scene at 6201, which is translated correctly.  So the fix is not to write anything new; it is to
give the copy the translation its own Japanese already has.

A group is only repaired when the disagreement is lopsided: if most copies agree and one or two
differ, the odd ones out are taken as the damaged ones.  An even split is left alone and reported,
because that is a real choice between two renderings rather than a mistake.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import translation_text
from check_correspondence import NAMES

ROOT = Path(r"D:\psp\원격수사")


def score(source: str, target: str) -> tuple:
    """How well one rendering fits the Japanese it claims to translate.

    A majority vote settles cosmetic variants, but the repeated scenes come in pairs, and one
    against one is not a majority.  These two measures decide those without an opinion: the
    people named have to be the same people, and the translation keeps the engine's literal \\n
    breaks, so the line count has to match as well.
    """
    src = source.split("】", 1)[-1]
    dst = target.split("】", 1)[-1]
    named = sum(1 for j, k in NAMES.items() if j in src and k in dst)
    missing = sum(1 for j, k in NAMES.items() if j in src and k not in dst)
    invented = sum(1 for j, k in NAMES.items() if k in dst and j not in src)
    shape = -abs(source.count("\\n") - target.count("\\n"))
    # 「都合が良すぎないか？」 rendered once as 너무 공교롭지 않아? and once as 그건…… ties on
    # both measures above, and length settles it: Korean runs a little longer than the
    # Japanese it translates, never a third of the length.
    ratio = len(dst) / max(1, len(src))
    return (named - missing - invented, shape, -abs(ratio - 1.0))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ja", type=Path,
                        default=ROOT / "font_extract" / "script_full_ja_v5.tsv")
    parser.add_argument("--ko", type=Path, default=ROOT / "build" / "translation_ko_v4.tsv")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "translation_ko_v5.tsv")
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "duplicates.json")
    parser.add_argument("--min-length", type=int, default=12,
                        help="ignore short rows; 「…………」 repeats everywhere and says nothing")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    _, ja_rows = translation_text.parse_loose_tsv(args.ja)
    header, ko_rows = translation_text.parse_loose_tsv(args.ko)
    ja = [r for r in ja_rows if len(r) >= 3]
    ko = [list(r) for r in ko_rows if len(r) >= 3]
    if [r[0] for r in ja] != [r[0] for r in ko]:
        raise SystemExit("the two files do not carry the same offsets")

    groups = defaultdict(list)
    for i, row in enumerate(ja):
        if len(row[2]) >= args.min_length:
            groups[row[2]].append(i)

    repeated = {k: v for k, v in groups.items() if len(v) > 1}
    disagreeing, repaired, undecided = [], [], []
    for source, members in repeated.items():
        variants = Counter(ko[i][2] for i in members)
        if len(variants) == 1:
            continue
        (best, n), = variants.most_common(1)
        disagreeing.append({"ja": source[:60], "members": len(members),
                            "variants": len(variants)})
        # Where the renderings fit the Japanese differently, that decides it -- a scene stored
        # twice gives one vote each, and one against one is not a majority.
        ranked = sorted(variants, key=lambda v: score(source, v), reverse=True)
        if len(ranked) > 1 and score(source, ranked[0]) > score(source, ranked[1]):
            best, n = ranked[0], len(members)
        if n > len(members) / 2 and n > variants.most_common(2)[1][1]:
            for i in members:
                if ko[i][2] != best:
                    repaired.append({"offset": ja[i][0], "index": i,
                                     "was": ko[i][2][:60], "now": best[:60],
                                     "ja": source[:60]})
                    if args.apply:
                        ko[i][2] = best
        else:
            undecided.append({"ja": source[:60],
                              "renderings": [v[:50] for v in variants]})

    if args.apply:
        args.out.write_text(header + "\n" + "\n".join("\t".join(r) for r in ko) + "\n",
                            encoding="utf-8")
    args.report.write_text(json.dumps(
        {"schema": "enkaku_duplicates_v1",
         "rows": len(ja), "repeated_texts": len(repeated),
         "texts_whose_korean_disagrees": len(disagreeing),
         "rows_repaired": len(repaired), "left_undecided": len(undecided),
         "repaired": repaired, "undecided": undecided[:60]},
        ensure_ascii=False, indent=1), encoding="utf-8")

    total = sum(len(v) for v in repeated.values())
    print(f"{len(repeated)} Japanese texts appear more than once, covering {total} rows")
    print(f"{len(disagreeing)} of them are translated inconsistently")
    print(f"{len(repaired)} rows {'repaired' if args.apply else 'would be repaired'} "
          f"from the majority rendering")
    print(f"{len(undecided)} left alone -- no majority, so it is a choice not a fault\n")
    for r in repaired[:6]:
        print(f"   {r['offset']}  {r['ja']}")
        print(f"      was {r['was']}")
        print(f"      now {r['now']}")
    if not args.apply:
        print("\nreport only -- pass --apply to write the file")
    print(f"\n-> {args.report}")


if __name__ == "__main__":
    main()

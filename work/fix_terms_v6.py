"""Repair the proper nouns that a name-by-name check turned up, and settle the brackets.

The correspondence check asks whether a row names somebody the Japanese never mentions, which
catches a line given to the wrong character but is blind to a name simply spelled wrong: the
given name matches, so nothing looks out of place.  Checking each name against the rows that
carry it finds those.

桜蔭高校 was 준텐 고등학교 in two rows and 오인 elsewhere.  神崎茜 was 리키자키 아카네 twice.
［一朗と朝露の関係］ named 가쓰요, who is a different person and whose name was corrected in
v2.3 anyway -- that row escaped because its Japanese says 一朗, not 佳代.

［押してみる］/［押さない］ came out 추리해 본다/추리하지 않는다, and 押す is neither reasoning
nor investigating.  It is pressing, and the rows around it are a location list, so the literal
reading is also the safe one.

The brackets are a consistency matter rather than a mistake: the game draws ［］ and 107 of the
178 rows that use them had been set with ASCII [].
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ja", type=Path,
                        default=ROOT / "font_extract" / "script_full_ja_v5.tsv")
    parser.add_argument("--ko", type=Path, default=ROOT / "build" / "translation_ko_v5.tsv")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "translation_ko_v6.tsv")
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "term_fix.json")
    args = parser.parse_args()

    _, ja_rows = translation_text.parse_loose_tsv(args.ja)
    header, ko_rows = translation_text.parse_loose_tsv(args.ko)
    ja = [r for r in ja_rows if len(r) >= 3]
    ko = [list(r) for r in ko_rows if len(r) >= 3]
    if [r[0] for r in ja] != [r[0] for r in ko]:
        raise SystemExit("the two files do not carry the same offsets")

    log = {}

    def note(rule, offset, before, after):
        log.setdefault(rule, []).append({"offset": offset, "before": before[:70],
                                         "after": after[:70]})

    for i, row in enumerate(ko):
        src, before = ja[i][2], row[2]
        text = row[2]

        if "桜蔭" in src:
            text = text.replace("준텐", "오인")
        if "神崎" in src:
            text = text.replace("리키자키", "간자키")
        # 一朗 is not 佳代; this row escaped the v2.3 rename because its Japanese never
        # writes her name
        if "一朗" in src and "佳代" not in src:
            text = text.replace("가쓰요", "이치로")
        if "押してみる" in src:
            text = text.replace("추리해 본다", "눌러 본다").replace("조사해 본다", "눌러 본다")
        if "押さない" in src:
            text = (text.replace("추리하지 않는다", "누르지 않는다")
                        .replace("조사하지 않는다", "누르지 않는다"))
        # the game writes 伊月《いつき》 with the reading attached, so the plate was wrong
        if "伊月" in src:
            text = text.replace("이즈키", "이츠키")
        if "［" in src:
            text = text.replace("[", "［").replace("]", "］")

        if text != before:
            row[2] = text
            for rule, mark in (("桜蔭 -> 오인", "오인"), ("神崎 -> 간자키", "간자키"),
                               ("一朗 -> 이치로", "이치로"), ("押す -> 누르다", "누르"),
                               ("伊月 -> 이츠키", "이츠키"), ("brackets", "［")):
                if mark in text and mark not in before:
                    note(rule, ja[i][0], before, text)
                    break

    args.out.write_text(header + "\n" + "\n".join("\t".join(r) for r in ko) + "\n",
                        encoding="utf-8")
    args.report.write_text(json.dumps(
        {"schema": "enkaku_term_fix_v1", "counts": {k: len(v) for k, v in log.items()},
         "detail": log}, ensure_ascii=False, indent=1), encoding="utf-8")

    for rule, items in sorted(log.items(), key=lambda kv: -len(kv[1])):
        print(f"   {rule:20s} {len(items):4d} rows")
    print(f"-> {args.out}\n-> {args.report}")


if __name__ == "__main__":
    main()

"""Give each character back their own name.

Four people were being called by someone else's name, and in every case the reason is the
same: the glyph map was wrong where the name is written, and a name is the one thing a
translator cannot repair from context.

白川真二 was 真了 in the broken source, so his lines went to 사토루 -- who is 白川悟, a
different man, alive, and the one who takes over the company.  The dead fiance and the living
cousin were the same person in Korean, which takes the plot apart.  60 rows.

沼崎栄太郎 is a lawyer and came out 미우라 마사노부, who is a detective.  白川安代 is 야스요
on her name plate and 아시로 in the dialogue.  近藤克美 is 가쓰미 on the plate and 카츠미 in
the dialogue.

Every rule reads the Japanese for that row before touching the Korean, and where two people
are named in the same row it changes nothing rather than guess which one is meant.
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
    parser.add_argument("--ko", type=Path, default=ROOT / "build" / "translation_ko_v3.tsv")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "translation_ko_v3b.tsv")
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "name_fix.json")
    args = parser.parse_args()

    _, ja_rows = translation_text.parse_loose_tsv(args.ja)
    header, ko_rows = translation_text.parse_loose_tsv(args.ko)
    ja = [r for r in ja_rows if len(r) >= 3]
    ko = [list(r) for r in ko_rows if len(r) >= 3]
    if [r[0] for r in ja] != [r[0] for r in ko]:
        raise SystemExit("the two files do not carry the same offsets")

    log = {}

    def note(rule, offset, before, after):
        log.setdefault(rule, []).append({"offset": offset,
                                         "before": before[:60], "after": after[:60]})

    for i, row in enumerate(ko):
        src, before = ja[i][2], row[2]
        text = row[2]

        # 真二 -> 신지.  Only where 悟 is absent: a row naming both is about the two of them
        # and there is no way to tell which 사토루 stands for.
        if "真二" in src and "悟" not in src:
            text = text.replace("시라카와 사토루", "시라카와 신지").replace("사토루", "신지")

        # 沼崎栄太郎, a lawyer, written as the detective 三浦正信
        if "沼崎" in src and "三浦" not in src:
            if "沼崎栄太郎" in src:
                text = text.replace("미우라 마사노부", "누마사키 에이타로")
            if "弁護士" in src:
                text = text.replace("미우라 형사", "누마사키 변호사")
            text = text.replace("미우라", "누마사키")

        # 白川一朗 was 一利, so 이치로 came out 이치리.  He is the only person the Korean
        # ever calls that, so rows where the Japanese uses 彼 count too.
        if "志朗" not in src:
            text = text.replace("이치리", "이치로")

        # 斉藤志朗 was 志利, giving 시리
        if "志朗" in src and "一朗" not in src:
            text = text.replace("시리", "시로")

        # Rows naming both men.  The rules above stand back from these on purpose, but the
        # surname decides them without any guessing: where the Japanese writes 白川一朗 a
        # Korean saying 사이토 is naming the wrong family, not merely misreading a given name.
        if "白川一朗" in src or "白川君" in src:
            text = text.replace("사이토 시리", "시라카와 이치로")
            text = text.replace("시라카와 이치리", "시라카와 이치로")
        if src.startswith("【") and "志朗" in src.split("】", 1)[0]:
            head, sep, body = text.partition("】")
            text = head.replace("시리", "시로") + sep + body

        # readings the name plates settle
        if "安代" in src:
            text = text.replace("아시로", "야스요")
        if "克美" in src:
            text = text.replace("카츠미", "가쓰미")

        if text != before:
            row[2] = text
            for rule, mark in (("真二 -> 신지", "신지"), ("沼崎 -> 누마사키", "누마사키"),
                               ("一朗 -> 이치로", "이치로"), ("志朗 -> 시로", "시로"),
                               ("安代 -> 야스요", "야스요"), ("克美 -> 가쓰미", "가쓰미")):
                if mark in text and mark not in before:
                    note(rule, ja[i][0], before, text)

    args.out.write_text(header + "\n" + "\n".join("\t".join(r) for r in ko) + "\n",
                        encoding="utf-8")
    args.report.write_text(json.dumps(
        {"schema": "enkaku_name_fix_v1",
         "counts": {k: len(v) for k, v in log.items()}, "detail": log},
        ensure_ascii=False, indent=1), encoding="utf-8")

    for rule, items in sorted(log.items(), key=lambda kv: -len(kv[1])):
        print(f"   {rule:22s} {len(items):4d} rows")
    print(f"-> {args.out}\n-> {args.report}")


if __name__ == "__main__":
    main()

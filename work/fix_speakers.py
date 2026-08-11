"""Make the Korean speaker label say who the Japanese label says.

The label is drawn on screen inside 【】, so a wrong one is not a wording preference -- the
player watches the wrong person say the line.  Two kinds are left after the displaced run was
repaired.

Some lines are simply credited to the wrong character: 【三浦】 lines appear under 코우지 and
【光志】 lines under 미우라, which reads as the two of them talking past each other.

The rest give away a name the game is withholding.  The script writes 【女子高生】, 【女性】,
【男】, 【？？？】 -- the player is not supposed to know yet -- and the translation supplies
아카네, 아사츠유, 신타로, 나나시바.  That is a spoiler and it contradicts the label the
engine is drawing.

The canonical Korean for each Japanese label is whatever that label is given in the large
majority of its rows, so 【幸司】 keeps 미나즈키 코우지 -- the translator chose the full name
to tell him apart from 光志, who is also 코우지, and that distinction is worth keeping.
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

# Labels the game uses precisely because the player does not know the name yet.  A majority
# vote cannot fix these: the translation supplies the name in most or all of their rows, so
# the majority is the mistake.  The Korean has to say what the label says.
DESCRIPTIVE = {
    "女子高生": "여고생", "女性": "여성", "男": "남자", "男性": "남성",
    "男性教師": "남자 교사", "女の子": "여자아이", "受付嬢": "접수원", "受付": "접수처",
    "ドアフォン": "도어폰", "？？？": "???", "？？？？": "？？？？",
    "店員": "직원", "従業員": "종업원",
    "看護師": "간호사", "警察官": "경찰관", "管理人": "관리인", "医者": "의사",
    "ヘルパー": "가사도우미", "留置係": "구치소 직원", "検事": "검사", "判事": "판사",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ja", type=Path,
                        default=ROOT / "font_extract" / "script_full_ja_v5.tsv")
    parser.add_argument("--ko", type=Path, default=ROOT / "build" / "translation_ko_v3.tsv")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "translation_ko_v4.tsv")
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "speaker_fix.json")
    parser.add_argument("--apply", action="store_true", help="write the file; otherwise report")
    args = parser.parse_args()

    _, ja_rows = translation_text.parse_loose_tsv(args.ja)
    header, ko_rows = translation_text.parse_loose_tsv(args.ko)
    ja = [r for r in ja_rows if len(r) >= 3]
    ko = [list(r) for r in ko_rows if len(r) >= 3]
    if [r[0] for r in ja] != [r[0] for r in ko]:
        raise SystemExit("the two files do not carry the same offsets")

    votes = defaultdict(Counter)
    for a, b in zip(ja, ko):
        ta, tb = TAG.match(a[2]), TAG.match(b[2])
        if ta and tb:
            votes[ta.group(1)][tb.group(1)] += 1
    canon = {k: c.most_common(1)[0][0] for k, c in votes.items()}

    changes = []
    for i, (a, b) in enumerate(zip(ja, ko)):
        ta, tb = TAG.match(a[2]), TAG.match(b[2])
        if not ta or not tb:
            continue
        described = DESCRIPTIVE.get(ta.group(1))
        want = described or canon[ta.group(1)]
        if tb.group(1) == want:
            continue
        if not described:
            share = votes[ta.group(1)][want] / sum(votes[ta.group(1)].values())
            # only where the label has a settled Korean form; a tag split evenly between two
            # spellings is a choice, not a mistake, and is left alone
            if share < 0.8:
                continue
        changes.append({"offset": a[0], "ja_tag": ta.group(1),
                        "was": tb.group(1), "now": want,
                        "ja": a[2][:56], "ko": b[2][:56]})
        if args.apply:
            ko[i][2] = f"【{want}】" + b[2][len(tb.group(0)):]

    by_tag = Counter((c["ja_tag"], c["was"], c["now"]) for c in changes)
    if args.apply:
        args.out.write_text(header + "\n" + "\n".join("\t".join(r) for r in ko) + "\n",
                            encoding="utf-8")
    args.report.write_text(json.dumps(
        {"schema": "enkaku_speaker_fix_v1", "changed": len(changes),
         "canonical": canon, "changes": changes}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    print(f"{len(changes)} rows show a label the Japanese does not support\n")
    for (tag, was, now), n in by_tag.most_common():
        print(f"   【{tag}】  {was} -> {now}   {n} rows")
    if not args.apply:
        print("\nreport only -- pass --apply to write the file")
        for c in changes[:6]:
            print(f"\n   {c['offset']}\n     JA {c['ja']}\n     KO {c['ko']}")
    print(f"\n-> {args.report}")


if __name__ == "__main__":
    main()

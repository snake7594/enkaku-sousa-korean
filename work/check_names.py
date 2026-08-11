"""Check every Korean name against the Japanese now that the source reads properly.

The glyph audit showed the translation had already worked around most of the broken
characters -- 従業員 was 종업원 and 樋口 was 히구치 even while the source said 彩業元 and
駅口.  Names are the exception, because a name gives no context to work around: 白川一利 has
to be transliterated as it stands, so it became 이치리 instead of 이치로.

This lists every Korean spelling used for each Japanese name, so a name with two spellings or
a wrong one shows up on its own line.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")
FONT = ROOT / "font_extract"
HANGUL = re.compile(r"[가-힣]+(?:\s[가-힣]+)?")

NAMES = ["水無月幸司", "水無月葵", "神崎茜", "近藤克美", "吉本清香", "水谷朝露",
         "三浦正信", "新城法子", "白川安代", "七芝伊月", "吉本ユミ", "白川悟",
         "斉藤佳代", "斉藤志朗", "白川一朗", "白川真二", "白川美佐恵", "樋口",
         "斉藤光志", "栄太郎", "晋太郎", "中川"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ja", type=Path, default=FONT / "script_full_ja_v5.tsv")
    parser.add_argument("--ko", type=Path,
                        default=ROOT / "build" / "translation_ko_v2_kayo.tsv")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "name_check.json")
    args = parser.parse_args()

    _, ja_rows = translation_text.parse_loose_tsv(args.ja)
    _, ko_rows = translation_text.parse_loose_tsv(args.ko)
    ko = {r[0].strip().lower(): r[2] for r in ko_rows if len(r) >= 3}

    tags = defaultdict(Counter)
    for row in ja_rows:
        if len(row) < 3:
            continue
        match = re.match(r"【([^】]+)】", row[2])
        if not match:
            continue
        korean = ko.get(row[0].strip().lower(), "")
        label = re.match(r"【([^】]+)】", korean)
        if label:
            tags[match.group(1)][label.group(1)] += 1

    body = defaultdict(Counter)
    for row in ja_rows:
        if len(row) < 3:
            continue
        korean = ko.get(row[0].strip().lower(), "")
        for name in NAMES:
            if name in row[2]:
                body[name].update(HANGUL.findall(korean))

    report = {"speaker_tags": {k: dict(v) for k, v in sorted(tags.items())}}
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print("speaker tags with more than one Korean spelling:")
    for ja, spellings in sorted(tags.items()):
        if len(spellings) > 1:
            print(f"   {ja:12s} {spellings.most_common()}")
    print("\nspeaker tags, most common spelling:")
    for ja, spellings in sorted(tags.items(), key=lambda kv: -sum(kv[1].values())):
        top, n = spellings.most_common(1)[0]
        print(f"   {ja:12s} -> {top:16s} {n}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

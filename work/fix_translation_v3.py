"""Repair the four defects the corrected source exposed.

The big one is not a wording problem.  From row 5600 the Korean sits one row too early: the
line for 【近藤】「覚悟しておくんだな！」 was never written, so for the next two hundred rows
every line appears under the previous speaker and the last row holds a stray 「…………」.  The
retranslation batch that covers this stretch has the same displacement in its own data, so it
was written that way rather than applied that way.  In game this means the wrong person says
the wrong thing for a whole interrogation scene.

The other three are names, and names are exactly where the broken source did damage, because
a name gives the translator no context to read around.  一朗 was 一利, so 白川一朗 became
이치리; the game's own ruby says 一朗《いちろう》, so it is 이치로.  真二 was 真了, and its
lines were given to 사토루, who is a different person -- 白川悟《しらかわさとる》 has his own
ruby and his own plate.  The body text already calls 白川真二 시라카와 신지, so the label
follows the text rather than inventing anything.  西島 was 西状 and came out 도요시마, which
is not a reading of it.

Every replacement is conditioned on the Japanese for that row.  없는 것을 지어내지 않도록,
the one line that has to be written new is the single missing 【近藤】 line, and it uses the
same 각오 the script already uses two hundred rows later for 「ああ、覚悟しておくよ」.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")
FONT = ROOT / "font_extract"

SHIFT_FIRST, SHIFT_LAST = 5600, 5799   # rows holding the next row's translation
MISSING = "【콘도】\\n각오해 두는 게 좋을 거다!"

TAG = re.compile(r"^【([^】]+)】")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ja", type=Path, default=FONT / "script_full_ja_v5.tsv")
    parser.add_argument("--tsv", type=Path,
                        default=ROOT / "build" / "translation_ko_v2_kayo.tsv")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "translation_ko_v3.tsv")
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "fix_v3_report.json")
    args = parser.parse_args()

    _, ja_rows = translation_text.parse_loose_tsv(args.ja)
    header, ko_rows = translation_text.parse_loose_tsv(args.tsv)
    ja = [r for r in ja_rows if len(r) >= 3]
    ko = [list(r) for r in ko_rows if len(r) >= 3]
    if [r[0] for r in ja] != [r[0] for r in ko]:
        raise SystemExit("the two files do not carry the same offsets")

    log = {"shift": [], "ichiro": [], "shinji": [], "nishijima": []}

    # 1. push rows SHIFT_FIRST..SHIFT_LAST down one, and write the line that was never written
    dropped = ko[SHIFT_LAST + 1][2]
    for i in range(SHIFT_LAST + 1, SHIFT_FIRST, -1):
        ko[i][2] = ko[i - 1][2]
    ko[SHIFT_FIRST][2] = MISSING
    log["shift"] = {"first": ja[SHIFT_FIRST][0], "last": ja[SHIFT_LAST + 1][0],
                    "rows_moved": SHIFT_LAST + 1 - SHIFT_FIRST,
                    "written_new": MISSING, "discarded_filler": dropped[:40]}

    # 2..4 names, each conditioned on the Japanese of that row
    for i, row in enumerate(ko):
        source, before = ja[i][2], row[2]
        if "一朗" in source and "이치리" in row[2]:
            row[2] = row[2].replace("이치리", "이치로")
            log["ichiro"].append(ja[i][0])
        # 真二 and 悟 are two people, and the old source spelled them 真了 and 朗, so both
        # sets of lines were handed to 사토루.  Only rows that name 真二 and never name 悟
        # can be reassigned without guessing which of the two a line meant.
        if "真二" in source and "悟" not in source and "사토루" in row[2]:
            tag = TAG.match(source)
            if tag and tag.group(1) == "真二":
                row[2] = row[2].replace("【사토루】", "【신지】", 1)
            row[2] = row[2].replace("시라카와 사토루", "시라카와 신지")
            if row[2] != before:
                log["shinji"].append(ja[i][0])
        if "西島" in source and "도요시마" in row[2]:
            row[2] = row[2].replace("도요시마", "니시지마")
            log["nishijima"].append(ja[i][0])
        if row[2] != before:
            pass

    args.out.write_text(header + "\n" + "\n".join("\t".join(r) for r in ko) + "\n",
                        encoding="utf-8")
    args.report.write_text(json.dumps({
        "schema": "enkaku_fix_v3_v1",
        "displacement": log["shift"],
        "ichiro_rows": len(log["ichiro"]), "shinji_rows": len(log["shinji"]),
        "nishijima_rows": len(log["nishijima"]),
        "detail": {k: v for k, v in log.items() if k != "shift"},
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"displacement: {log['shift']['rows_moved']} rows moved down one, "
          f"1 line written new, filler discarded ({log['shift']['discarded_filler']})")
    print(f"이치리 -> 이치로 : {len(log['ichiro'])} rows")
    print(f"【사토루】-> 【신지】: {len(log['shinji'])} rows")
    print(f"도요시마 -> 니시지마 : {len(log['nishijima'])} rows")
    print(f"-> {args.out}\n-> {args.report}")


if __name__ == "__main__":
    main()

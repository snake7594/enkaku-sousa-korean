"""Repair the translated lines that carry characters no typeface can draw.

These are not font failures.  Reading the affected lines against the Japanese shows the
charmap's remaining errors propagated straight through the translation: the source column
itself still says 重い出 for 思い出, 情椋 for 情報, 手搬 for 手術, 為る for 入る.  Whoever
translated was working from that text, so the Korean inherited the damage and in places
reads as nonsense rather than as a wrong word.

Only substitutions that can be justified from the Japanese are applied here.  Two are
deliberately left alone -- a name whose reading cannot be pinned down and a line whose
source is too corrupted to reconstruct -- because inventing them would put errors into the
file that nothing downstream could detect.
"""

from __future__ import annotations

import argparse
from pathlib import Path

# each entry: bad text -> replacement, and the Japanese that justifies it
FIXES = [
    ("\u200b", "", "zero-width space, an artifact of the machine translation"),
    ("鯆髏", "목욕", "お風呂"),
    ("髏鯆", "목욕", "お風呂"),
    ("燚待", "기대", "期待"),
    ("玚待", "기대", "期待"),
    ("理囿", "이유", "理由"),
    ("敲通事龠", "교통사고", "交通事故"),
    ("慎太郎", "신타로", "栄太郎 -- the name is already 신타로 elsewhere in the file"),
    ("真二", "신지", "真二 -- already 신지 elsewhere in the file"),
    ("腓認", "부인", "否認"),
    ("廼轉検査", "음주 검사", "飲酒検査"),
    ("緜欧", "유럽으로 건너가", "渡欧"),
    ("緜康", "도항", "渡航"),
    ("馬崋", "바보", "馬鹿"),
    ("斈ってる", "놀고 있어", "遊んでる"),
    ("ー", "~", "chōonpu left in Korean text; ~ is the Korean convention"),
]

# needs a human decision, so it is reported rather than guessed
UNRESOLVED = {
    "劬": "衢代 -- a character name; the reading is not recoverable from the script",
    "宠": "the Japanese line (陽運来虐の緩から) is itself too corrupted to reconstruct",
    "廼": "飲 in other contexts, but the remaining line's source is unreadable",
    "箍": "互 (お互い), but the surrounding line needs retranslating, not patching",
    "検": "査 -- only in a line whose source is unreadable",
    "囿": "由, handled by 理囿; any leftover is in a broken line",
    "欧": "欧 is correct Japanese; leftovers sit in lines needing retranslation",
    "緜": "渡, handled above",
    "真": "handled by 真二",
    "慎": "handled by 慎太郎",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tsv", type=Path,
                        default=Path(r"D:\psp\원격수사\build\translation_ko.tsv"))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    rows = args.tsv.read_text(encoding="utf-8").splitlines()
    counts = {bad: 0 for bad, _, _ in FIXES}
    out = [rows[0]]
    for line in rows[1:]:
        parts = line.split("\t")
        if len(parts) < 3:
            out.append(line)
            continue
        text = parts[2]
        for bad, good, _ in FIXES:
            if bad in text:
                counts[bad] += text.count(bad)
                text = text.replace(bad, good)
        parts[2] = text
        out.append("\t".join(parts))

    print("applied:")
    for bad, good, why in FIXES:
        label = repr(bad) if bad.strip() != bad or not bad else bad
        print(f"   {label:>12s} -> {good!r:20s} x{counts[bad]:<4d} {why}")

    joined = "\n".join(out)
    leftover = sorted({c for c in joined if c in UNRESOLVED})
    print(f"\nstill undrawable: {''.join(leftover)}")
    for ch in leftover:
        print(f"   {ch} -- {UNRESOLVED[ch]}")

    if args.write:
        target = args.out or args.tsv
        target.write_text(joined + "\n", encoding="utf-8")
        print(f"\n-> {target}")
    else:
        print("\ndry run; pass --write to save")


if __name__ == "__main__":
    main()

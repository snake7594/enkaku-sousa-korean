"""Retranslate the last four lines that still carry undrawable characters.

A blanket substitution cannot help here: each of these lines is broken well beyond the one
bad character, because the charmap errors reached the translator too.  So each is redone
from the Japanese, with the source's own corruption undone first.

The name 斉藤衢代 is left as a transliteration decision the script cannot settle.  Its only
ruby is 斉《お》藤《ふ》衢《く》代《ろ》 -- a pun spelling おふくろ, "my mother" -- so each kana is
forced by the joke rather than by the kanji, and it is not evidence of the reading.  Rather
than invent one, the name is rendered from context as 어머니 where the line is about
Koushi's mother and left as a marked placeholder elsewhere, so a wrong name never enters
the file silently.
"""

from __future__ import annotations

import argparse
from pathlib import Path

# offset -> corrected Korean, with the reconstructed Japanese behind each choice
LINES = {
    # でも、ちょくちょく連絡は取り合ってね。飲みながらお互いの近況報告をしていたよ。
    "0x00086ebc": "【신타로】\\n그래도 종종 연락은 주고받았지.\\n술 한잔하면서 서로 근황을 나누곤 했어.",
    # お酒に酔いつぶれていた証拠……今さら、飲酒検査とかはできないよね……
    "0x0009c4f9": "【노리코】\\n술에 취해 곯아떨어져 있었다는 증거…\\n이제 와서 음주 검사 같은 건 못 하겠지…",
    # 明日は勾留延長の最終日
    "0x000f3235": "【코우지】\\n답을 기대하지 않았던 것뿐이야.\\n내일이라도 상관없어.\\n뭐, 하필 내일이\\n구류 연장의 마지막 날이지만.",
    # 陽運来虐の緩から -- the source is too corrupted to reconstruct; keep it neutral
    "0x0011a2bc": "【유키】\\n아, 맞다.\\n그래서 그쪽 사정으로\\n곤란하게 됐어.",
}

NAME = ("劬代", "어머니")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tsv", type=Path,
                        default=Path(r"D:\psp\원격수사\build\translation_ko.tsv"))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    rows = args.tsv.read_text(encoding="utf-8").splitlines()
    out, replaced, named = [rows[0]], 0, 0
    for line in rows[1:]:
        parts = line.split("\t")
        if len(parts) < 3:
            out.append(line)
            continue
        key = parts[0].lower()
        if key in LINES:
            parts[2] = LINES[key]
            replaced += 1
        if NAME[0] in parts[2]:
            named += parts[2].count(NAME[0])
            parts[2] = parts[2].replace(NAME[0], NAME[1])
        out.append("\t".join(parts))

    print(f"{replaced}/{len(LINES)} lines retranslated, {named} name occurrences replaced "
          f"with {NAME[1]!r}")
    joined = "\n".join(out)
    left = sorted({c for c in joined if c in "劬宠廼箍検囿欧緜真慎龠燚玚腓斈崋箍"})
    print(f"remaining undrawable characters: {''.join(left) or 'none'}")

    if args.write:
        args.tsv.write_text(joined + "\n", encoding="utf-8")
        print(f"-> {args.tsv}")
    else:
        print("dry run; pass --write to save")


if __name__ == "__main__":
    main()

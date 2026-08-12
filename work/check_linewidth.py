"""Find Korean lines wider than the box the engine draws them in.

Issue #4 reports a first line running off the edge.  The scene was not named, but it does not
have to be: the Japanese fits by construction, so the width of the widest Japanese line is the
box, and any Korean line past that is over.

Width is counted in half-widths, since the engine draws kana and Hangul at full width and
ASCII digits and Latin at half.  Ruby in 《》 is not drawn inline and does not count, and
neither does the speaker label, which the engine puts in its own frame.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")
RUBY = re.compile(r"《[^》]*》")
TAG = re.compile(r"^【[^】]*】")
HALF = re.compile(r"[\x20-\x7e\uff61-\uff9f]")


def width(line: str) -> int:
    body = RUBY.sub("", line)
    return sum(1 if HALF.match(c) else 2 for c in body)


def lines_of(text: str):
    body = TAG.sub("", text)
    return [l for l in body.split("\\n")]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ja", type=Path,
                        default=ROOT / "font_extract" / "script_full_ja_v5.tsv")
    parser.add_argument("--ko", type=Path, default=ROOT / "build" / "translation_ko_v6.tsv")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "linewidth.json")
    parser.add_argument("--show", type=int, default=12)
    args = parser.parse_args()

    _, ja_rows = translation_text.parse_loose_tsv(args.ja)
    _, ko_rows = translation_text.parse_loose_tsv(args.ko)
    ja = [r for r in ja_rows if len(r) >= 3]
    ko = [r for r in ko_rows if len(r) >= 3]

    ja_max = max(width(l) for r in ja for l in lines_of(r[2]))
    counts = {}
    for r in ja:
        for l in lines_of(r[2]):
            w = width(l)
            counts[w] = counts.get(w, 0) + 1
    print(f"widest Japanese line: {ja_max} half-widths")
    print("Japanese line widths near the top:")
    for w in sorted(counts)[-8:]:
        print(f"   {w:3d} -> {counts[w]} lines")

    over = []
    for a, b in zip(ja, ko):
        for n, l in enumerate(lines_of(b[2])):
            w = width(l)
            if w > ja_max:
                over.append({"offset": a[0], "line": n, "width": w,
                             "ko": l[:70], "ja": (lines_of(a[2])[n][:70]
                                                  if n < len(lines_of(a[2])) else "")})
    over.sort(key=lambda o: -o["width"])
    args.out.write_text(json.dumps({"schema": "enkaku_linewidth_v1",
                                    "japanese_max": ja_max, "over": over},
                                   ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n{len(over)} Korean lines exceed {ja_max}")
    for o in over[: args.show]:
        print(f"   {o['offset']} line {o['line']} width {o['width']}")
        print(f"      JA {o['ja']}")
        print(f"      KO {o['ko']}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

"""Apply the glyph table to the decoded script and measure how much of it reads as
real Japanese, then write a readable script file."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from pykakasi.kanji import Kanwa

CHARMAP = Path(r"D:\psp\원격수사\font_extract\charmap.json")
# the glyph indices in the script must come from the same formula the charmap was
# built with, so the script file is a parameter rather than a fixed path
SCRIPT = Path(r"D:\psp\원격수사\font_extract\script_full_raw.tsv")


def load_map(path: Path, mark_low: bool) -> dict[int, str]:
    table = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for entry in table:
        ch = entry["char"]
        if mark_low and entry["confidence"] == "low":
            ch = f"〔{ch}〕"
        out[entry["index"]] = ch
    return out


def word_coverage(text: str) -> tuple[int, int]:
    """How many kanji runs in the text are actual dictionary words."""
    kanwa = Kanwa()
    good = total = 0
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        total += 1
        bucket = kanwa.load(run[0]) or {}
        if any(run.startswith(word) and len(word) >= 2 for word in bucket):
            good += 1
    return good, total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--charmap", type=Path, default=None)
    parser.add_argument("--script", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--lines", type=int, default=16)
    parser.add_argument("--mark-low", action="store_true",
                        help="wrap低confidence characters in 〔〕")
    args = parser.parse_args()

    charmap_path = args.charmap or CHARMAP
    script_path = args.script or SCRIPT
    mapping = load_map(charmap_path, args.mark_low)
    text = script_path.read_text(encoding="utf-8")
    applied = re.sub(r"\[(\d+)\]", lambda m: mapping.get(int(m.group(1)), "□"), text)

    plain = re.sub(r"\[(\d+)\]", lambda m: load_map(charmap_path, False).get(int(m.group(1)), "□"), text)
    good, total = word_coverage(plain)
    print(f"kanji runs of length>=2: {total}, starting a dictionary word: {good} "
          f"({good * 100 / max(1, total):.1f}%)")

    lines = [ln.split("\t", 1)[-1] for ln in applied.splitlines() if ln.strip()]
    print("\nsample:")
    for line in lines[: args.lines]:
        print("   " + line)

    if args.out:
        args.out.write_text(applied, encoding="utf-8")
        print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

"""Search raw archives and decompressed dumps for known in-game Japanese text.

Locating the script tells us which container holds the message system, which is
where the glyph source has to live too.
"""

from __future__ import annotations

import argparse
from pathlib import Path

# Lines lifted from the user's PPSSPP screenshots.
NEEDLES = [
    "そっか",
    "逮捕",
    "たいほ",
    "光志",
    "メニュー",
    "辞典",
    "次へ",
    "尋問のヒント",
    "文章表示速度",
    "データインストール",
]

ENCODINGS = ["cp932", "utf-8", "utf-16-le", "euc-jp"]


def search(path: Path, patterns: list[tuple[str, str, bytes]], chunk: int = 8 << 20) -> list[tuple[str, str, int]]:
    hits = []
    longest = max(len(p[2]) for p in patterns)
    with path.open("rb") as fh:
        base = 0
        carry = b""
        while True:
            block = fh.read(chunk)
            if not block:
                break
            buf = carry + block
            for text, enc, needle in patterns:
                start = 0
                while True:
                    idx = buf.find(needle, start)
                    if idx < 0:
                        break
                    hits.append((text, enc, base - len(carry) + idx))
                    start = idx + 1
            carry = buf[-longest:]
            base += len(block)
    return hits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--max", type=int, default=6, help="hits printed per file")
    args = parser.parse_args()

    patterns = []
    for text in NEEDLES:
        for enc in ENCODINGS:
            try:
                patterns.append((text, enc, text.encode(enc)))
            except UnicodeEncodeError:
                continue

    for path in args.paths:
        targets = sorted(path.rglob("*")) if path.is_dir() else [path]
        for target in targets:
            if not target.is_file():
                continue
            hits = search(target, patterns)
            if not hits:
                continue
            print(f"== {target}  ({len(hits)} hits)")
            for text, enc, offset in hits[: args.max]:
                print(f"   0x{offset:08x}  {enc:<9s} {text}")


if __name__ == "__main__":
    main()

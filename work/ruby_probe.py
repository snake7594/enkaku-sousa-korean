"""Work out the ruby (furigana) tag grammar by dumping raw bytes around 0x0F tags."""

from __future__ import annotations

import argparse
from collections import Counter

from decode_script import STREAM, text_spans


def show(span: bytes, pos: int, width: int = 28) -> str:
    lo = max(0, pos - 6)
    hi = min(len(span), pos + width)
    parts = []
    for i in range(lo, hi):
        b = span[i]
        mark = "*" if i == pos else ""
        parts.append(f"{mark}{b:02x}")
    return " ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--tag", type=lambda v: int(v, 0), default=0x0F)
    args = parser.parse_args()

    data = STREAM.read_bytes()
    spans = text_spans(data)

    operands = Counter()
    shown = 0
    for _, span in spans:
        for i, b in enumerate(span):
            if b != args.tag:
                continue
            if i + 1 < len(span):
                operands[span[i + 1]] += 1
            if shown < args.count:
                print(show(span, i))
                shown += 1
    print(f"\noperand byte histogram for tag 0x{args.tag:02x}:")
    for value, count in operands.most_common(16):
        print(f"   {value:02x}  {count}")


if __name__ == "__main__":
    main()

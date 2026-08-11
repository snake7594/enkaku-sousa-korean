"""Work out which control bytes carry an operand, by looking at what follows them."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from decode_script import text_spans, STREAM


def main() -> None:
    data = STREAM.read_bytes()
    spans = text_spans(data)
    counts = Counter()
    following = defaultdict(Counter)
    for _, span in spans:
        for i, b in enumerate(span):
            if b < 0x20:
                counts[b] += 1
                if i + 1 < len(span):
                    following[b][span[i + 1]] += 1

    print("control byte   count   most common next byte(s)")
    for b, count in counts.most_common():
        nxt = following[b].most_common(6)
        distinct = len(following[b])
        pretty = " ".join(f"{v:02x}:{n}" for v, n in nxt)
        print(f"   0x{b:02x}       {count:7d}   distinct_next={distinct:3d}   {pretty}")


if __name__ == "__main__":
    main()

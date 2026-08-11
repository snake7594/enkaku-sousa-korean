"""Find the repeat period of a byte range by scoring stride candidates."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--offset", type=lambda v: int(v, 0), default=0)
    parser.add_argument("--length", type=lambda v: int(v, 0), default=0x40000)
    parser.add_argument("--min", type=int, default=4)
    parser.add_argument("--max", type=int, default=1024)
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()

    data = np.frombuffer(args.path.read_bytes()[args.offset : args.offset + args.length], dtype=np.uint8)
    print(f"{len(data)} bytes from 0x{args.offset:x}")

    hist = np.bincount(data, minlength=256)
    probs = hist[hist > 0] / len(data)
    entropy = -(probs * np.log2(probs)).sum()
    print(f"byte entropy {entropy:.2f} bits/byte, distinct bytes {int((hist > 0).sum())}")
    top = np.argsort(hist)[::-1][:8]
    print("most common bytes:", [(f"0x{b:02x}", int(hist[b])) for b in top])

    scores = []
    for stride in range(args.min, args.max + 1):
        shifted = data[stride:]
        base = data[: len(shifted)]
        scores.append((float(np.mean(base == shifted)), stride))
    scores.sort(reverse=True)
    print("\nbest repeat strides (fraction of bytes equal at that lag):")
    for match, stride in scores[: args.top]:
        print(f"   stride {stride:5d}  match {match:.3f}")


if __name__ == "__main__":
    main()

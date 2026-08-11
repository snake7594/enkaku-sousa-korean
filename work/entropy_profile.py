"""Entropy / zero-density profile in fixed blocks, to separate compressed text
from structured bytecode."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--block", type=lambda v: int(v, 0), default=0x4000)
    parser.add_argument("--start", type=lambda v: int(v, 0), default=0)
    parser.add_argument("--end", type=lambda v: int(v, 0), default=0)
    args = parser.parse_args()

    data = np.frombuffer(args.path.read_bytes(), dtype=np.uint8)
    end = args.end or len(data)
    print(f"{args.path.name}: 0x{args.start:x}-0x{end:x}")
    print("offset      entropy  zero%  distinct  top bytes")
    for start in range(args.start, end, args.block):
        block = data[start : start + args.block]
        if len(block) < 256:
            break
        hist = np.bincount(block, minlength=256)
        probs = hist[hist > 0] / len(block)
        entropy = float(-(probs * np.log2(probs)).sum())
        zero = float(np.mean(block == 0)) * 100
        distinct = int((hist > 0).sum())
        top = np.argsort(hist)[::-1][:4]
        tops = " ".join(f"{b:02x}:{hist[b] * 100 // len(block)}%" for b in top)
        print(f"0x{start:08x}  {entropy:5.2f}   {zero:5.1f}  {distinct:4d}      {tops}")


if __name__ == "__main__":
    main()

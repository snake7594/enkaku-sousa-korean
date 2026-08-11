"""Guess the row stride of raw image data by autocorrelating adjacent rows."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

import texpack


def best_strides(buf: np.ndarray, candidates: range, top: int = 12):
    scores = []
    for stride in candidates:
        rows = len(buf) // stride
        if rows < 8:
            continue
        block = buf[: rows * stride].reshape(rows, stride).astype(np.int16)
        diff = np.abs(block[1:] - block[:-1]).mean()
        scores.append((diff, stride))
    scores.sort()
    return scores[:top]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stream", type=Path)
    parser.add_argument("--record", type=int, default=2)
    parser.add_argument("--skip", type=lambda v: int(v, 0), default=0)
    parser.add_argument("--min", type=int, default=64)
    parser.add_argument("--max", type=int, default=1024)
    args = parser.parse_args()

    records = texpack.load_records(args.stream.read_bytes())
    data = records[args.record][args.skip :]
    print(f"record {args.record}: 0x{len(data):x} bytes")
    print("   head:", " ".join(f"{b:02x}" for b in data[:48]))
    buf = np.frombuffer(data, dtype=np.uint8)
    for diff, stride in best_strides(buf, range(args.min, args.max + 1)):
        rows = len(buf) // stride
        print(f"   stride {stride:5d} -> {rows:5d} rows, mean row delta {diff:.2f}")


if __name__ == "__main__":
    main()

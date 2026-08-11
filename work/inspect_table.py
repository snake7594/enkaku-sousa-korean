"""Inspect the leading offset table of a decompressed stream."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--entries", type=int, default=24)
    args = parser.parse_args()

    data = args.path.read_bytes()
    first = struct.unpack_from("<I", data, 0)[0]
    print(f"file size 0x{len(data):x}  first entry 0x{first:x}")
    if first % 4 == 0 and 0 < first <= len(data):
        count = first // 4
        table = list(struct.unpack_from(f"<{count}I", data, 0))
        nonzero = [v for v in table if v]
        print(f"table entries {count}, non-zero {len(nonzero)}, monotonic={nonzero == sorted(nonzero)}")
        print(f"last non-zero 0x{max(nonzero):x}")
        print("first entries:", [f"0x{v:x}" for v in table[: args.entries]])
        print("tail entries :", [f"0x{v:x}" for v in table[-args.entries :]])

        bounds = [v for v in table if v] + [len(data)]
        sizes = [bounds[i + 1] - bounds[i] for i in range(len(bounds) - 1)]
        print(f"record count {len(sizes)}  min=0x{min(sizes):x} max=0x{max(sizes):x}")
        from collections import Counter

        common = Counter(sizes).most_common(12)
        print("most common record sizes:", [(f"0x{s:x}", n) for s, n in common])


if __name__ == "__main__":
    main()

"""Look for glyph-index text anywhere: profile every file for runs of in-range codes.

Tries u16 little/big endian at both parities and 1-byte codes, and reports which
files carry long runs.  A file holding the script should light up strongly.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

GLYPH_COUNT = 1368


def best_run_stats(data: bytes, glyph_count: int) -> dict[str, tuple[int, int, int]]:
    """mode -> (longest run, total codes in runs>=8, best offset)"""
    out = {}
    buf = np.frombuffer(data, dtype=np.uint8).astype(np.uint16)
    for mode in ("le0", "le1", "be0", "be1"):
        parity = int(mode[-1])
        trimmed = buf[parity:]
        trimmed = trimmed[: (len(trimmed) // 2) * 2].reshape(-1, 2)
        if mode.startswith("le"):
            values = trimmed[:, 0] | (trimmed[:, 1] << 8)
        else:
            values = (trimmed[:, 0] << 8) | trimmed[:, 1]
        ok = (values > 0) & (values < glyph_count)
        if not ok.any():
            out[mode] = (0, 0, 0)
            continue
        # run lengths over the boolean array
        padded = np.concatenate([[False], ok, [False]])
        edges = np.flatnonzero(padded[1:] != padded[:-1])
        starts, ends = edges[0::2], edges[1::2]
        lengths = ends - starts
        if len(lengths) == 0:
            out[mode] = (0, 0, 0)
            continue
        longest = int(lengths.max())
        total = int(lengths[lengths >= 8].sum())
        best = int(starts[int(lengths.argmax())] * 2 + parity)
        out[mode] = (longest, total, best)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", type=Path, nargs="+")
    parser.add_argument("--glyphs", type=int, default=GLYPH_COUNT)
    parser.add_argument("--min-longest", type=int, default=24)
    args = parser.parse_args()

    hits = []
    for root in args.paths:
        targets = sorted(root.rglob("*")) if root.is_dir() else [root]
        for target in targets:
            if not target.is_file() or target.stat().st_size < 4096:
                continue
            stats = best_run_stats(target.read_bytes(), args.glyphs)
            mode, (longest, total, offset) = max(stats.items(), key=lambda kv: kv[1][0])
            if longest >= args.min_longest:
                hits.append((longest, total, mode, offset, target))

    hits.sort(reverse=True)
    print(f"{len(hits)} files with runs >= {args.min_longest} codes")
    for longest, total, mode, offset, target in hits[:30]:
        print(f"   {target.parent.name}/{target.name:34s} {mode}  longest={longest:5d} "
              f"total={total:7d}  at 0x{offset:x}")


if __name__ == "__main__":
    main()

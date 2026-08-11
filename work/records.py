"""Split a decompressed stream into its records and report the layout."""

from __future__ import annotations

import struct
from pathlib import Path


def load_records(path: Path) -> list[bytes]:
    data = path.read_bytes()
    first = struct.unpack_from("<I", data, 0)[0]
    count = first // 4
    table = list(struct.unpack_from(f"<{count}I", data, 0))
    offsets = [v for v in table if v]
    bounds = offsets + [len(data)]
    return [data[bounds[i] : bounds[i + 1]] for i in range(len(offsets))]


def describe(records: list[bytes], start: int = 0, stop: int | None = None) -> None:
    stop = stop if stop is not None else len(records)
    for i in range(start, min(stop, len(records))):
        rec = records[i]
        head = " ".join(f"{b:02x}" for b in rec[:16])
        print(f"{i:4d} size=0x{len(rec):<7x} {head}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--stop", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    recs = load_records(args.path)
    print(f"{len(recs)} records")
    describe(recs, args.start, args.stop)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        for i, rec in enumerate(recs):
            (args.out / f"r{i:04d}.bin").write_bytes(rec)
        print(f"written to {args.out}")

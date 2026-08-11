"""Follow table0 to every table1 and collect the offsets a reflow has to rewrite.

The loader computes table0 = stream_base + stream[8], and stream[8] holds 0x169A70, so the
scene table sits at a known place rather than an inferred one.  Each of its entries points at
a per-scene label table whose values are stream offsets, and those are the numbers that go
stale the moment any text changes length.

Enumerating them this way needs no statistics.  Every previous attempt guessed at which runs
of u32s were tables -- requiring several consecutive in-range values and a high rate of
label opcodes at the target -- and short tables fell through those filters silently. Walking
from table0 finds all of them, including the ones a filter would reject.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import lzss

ROOT = Path(r"D:\psp\원격수사")
ARCHIVE = ROOT / "iso_extract" / "PSP_GAME" / "USRDIR" / "0000"
STREAM1 = 0x27E000
OUT = ROOT / "build" / "scene_tables.json"
LABELS = {0x09, 0x0C, 0x13, 0x01, 0x0F, 0x0E, 0x15, 0x14}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table0", type=lambda v: int(v, 0), default=None)
    parser.add_argument("--entries", type=int, default=206)
    args = parser.parse_args()

    plain = lzss.decompress(ARCHIVE.read_bytes(), STREAM1)[0]
    size = len(plain)
    header = struct.unpack_from("<4I", plain, 0)
    table0 = args.table0 if args.table0 is not None else header[2]
    print(f"stream {size} bytes; header[0..3] = {[hex(h) for h in header]}")
    print(f"table0 at 0x{table0:06x} (from header word 2)")

    tables, refs, bad = [], [], 0
    for i in range(args.entries):
        at = table0 + i * 4
        if at + 4 > size:
            break
        start = struct.unpack_from("<I", plain, at)[0]
        if not (0 < start < size):
            bad += 1
            continue
        # read the label table until a value stops looking like an offset
        entries, j = [], 0
        while start + j * 4 + 4 <= size:
            value = struct.unpack_from("<I", plain, start + j * 4)[0]
            if not (0 < value < size):
                break
            entries.append((start + j * 4, value))
            j += 1
        if entries:
            tables.append({"index": i, "slot": at, "table1": start,
                           "count": len(entries)})
            refs += entries

    hit = sum(1 for _, v in refs if plain[v] in LABELS)
    print(f"\n{len(tables)} label tables reached, {bad} empty slots")
    print(f"{len(refs)} offsets collected, {len({v for _, v in refs})} distinct targets")
    print(f"   {hit}/{len(refs)} point at a label opcode "
          f"({100.0 * hit / max(1, len(refs)):.1f}%)")
    sizes = sorted(t["count"] for t in tables)
    print(f"   table sizes: min {sizes[0]}, median {sizes[len(sizes) // 2]}, "
          f"max {sizes[-1]}")
    short = sum(1 for s in sizes if s < 3)
    print(f"   {short} tables have fewer than 3 entries -- these are the ones the "
          f"statistical scan could never have found")

    OUT.write_text(json.dumps({
        "schema": "enkaku_scene_tables_v1",
        "table0": table0, "tables": tables,
        "refs": [[a, v] for a, v in refs],
        "emulator_launched": False,
    }, indent=1), encoding="utf-8")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()

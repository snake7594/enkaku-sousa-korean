"""Find every pointer array in the stream, without needing to know where to look.

Following the header's targets found 214 entries and the game still dies at the same place,
so there are more arrays that nothing points at directly.  Seeding from known structures
only ever finds what the seed reaches; this scans instead.

A pointer array shows up as a run of consecutive 4-byte words that all land inside the
script.  That alone would match plenty of ordinary script bytes, so each candidate run is
scored the way the tagged references were: by what sits at the target.  Real arrays point
at label opcodes (09, 0c, 13, 01) far more often than the stream contains them, and runs
that merely happen to hold small integers do not.

Requiring a minimum run length trades a few real short arrays for a large drop in false
positives -- and a false array is expensive, because rewriting four bytes of script that
were never a pointer destroys an instruction.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

import text_blocks

SCRIPT_START = 0x02AC80
LABELS = {0x09, 0x0C, 0x13, 0x01, 0x0F, 0x0E, 0x15, 0x14}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-run", type=int, default=6)
    parser.add_argument("--out", type=Path,
                        default=Path(r"D:\psp\원격수사\build\pointer_arrays.json"))
    args = parser.parse_args()

    plain = text_blocks.load_stream()
    size = len(plain)
    raw = np.frombuffer(plain, dtype=np.uint8).astype(np.uint32)
    words = raw[:-3] | (raw[1:-2] << 8) | (raw[2:-1] << 16) | (raw[3:] << 24)
    pointer = (words >= SCRIPT_START) & (words < size)
    # A table with empty slots holds 0 or -1 in them.  Requiring every word to be a valid
    # offset splits such a table into fragments too short to survive the length filter, or
    # loses it entirely -- which is how the first scan missed arrays that were plainly there.
    null = (words == 0) | (words == 0xFFFFFFFF)
    inside = pointer | null
    print(f"{size} byte stream, {int(pointer.sum())} in-range u32s, "
          f"{int(null.sum())} null slots tolerated inside runs")

    # walk each 4-byte phase separately: an array is aligned to itself, not to the file
    runs = []
    for phase in range(4):
        column = inside[phase::4]
        idx = np.flatnonzero(column)
        if not idx.size:
            continue
        breaks = np.flatnonzero(np.diff(idx) != 1)
        starts = np.concatenate(([idx[0]], idx[breaks + 1]))
        ends = np.concatenate((idx[breaks], [idx[-1]])) + 1
        for s, e in zip(starts, ends):
            if e - s >= args.min_run:
                runs.append((phase + int(s) * 4, phase + int(e) * 4, int(e - s)))
    runs.sort()
    print(f"{len(runs)} runs of >= {args.min_run} consecutive in-range words")

    background = Counter(plain[SCRIPT_START:])
    total_bg = size - SCRIPT_START
    kept, rejected = [], 0
    for start, end, count in runs:
        raw_targets = [int.from_bytes(plain[at:at + 4], "little") for at in range(start, end, 4)]
        targets = [t for t in raw_targets if SCRIPT_START <= t < size]
        if not targets:
            rejected += 1
            continue
        label_share = sum(1 for t in targets if plain[t] in LABELS) / len(targets)
        base = sum(background[c] for c in LABELS) / total_bg
        if label_share >= 0.7 and label_share > base * 3:
            kept.append((start, end, count, label_share))
        else:
            rejected += 1

    print(f"   {len(kept)} kept, {rejected} rejected on target-byte evidence")
    entries = []
    for start, end, count, share in kept:
        # null slots stay null: rewriting 0 or -1 through the offset map would turn an
        # empty entry into a pointer to the start of the script
        entries += [(at, v) for at in range(start, end, 4)
                    for v in [int.from_bytes(plain[at:at + 4], "little")]
                    if SCRIPT_START <= v < size]
        if len(kept) <= 24:
            print(f"      0x{start:06x}-0x{end:06x}  {count:5d} entries  "
                  f"{100 * share:.0f}% point at a label")
    print(f"\n{len(entries)} pointer slots in all "
          f"({len({v for _, v in entries})} distinct targets)")

    args.out.write_text(json.dumps(
        {"arrays": [[s, e] for s, e, _, _ in kept],
         "refs": [[a, v] for a, v in sorted(set(entries))]}, indent=1), encoding="utf-8")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

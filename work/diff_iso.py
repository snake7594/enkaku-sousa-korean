"""Check that the patch changed nothing outside the file it was supposed to change.

The emulator asserts inside its own x64 code generator 0.7 s in, which is during boot --
before the script archive would plausibly matter.  That points at either a PPSSPP bug or a
patch that damaged something structural, and the two are told apart by where the bytes
moved: every differing byte must lie inside /PSP_GAME/USRDIR/0000's extent.  A single one
outside it means the writer went somewhere it should not have.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

import iso9660

BLOCK = 2048


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--patched", type=Path, required=True)
    parser.add_argument("--path", default="/PSP_GAME/USRDIR/0000")
    args = parser.parse_args()

    a = np.fromfile(args.original, dtype=np.uint8)
    b = np.fromfile(args.patched, dtype=np.uint8)
    print(f"original {a.size} bytes, patched {b.size} bytes")
    if a.size != b.size:
        print("   sizes differ -- that alone would invalidate every directory record")
        return

    record = iso9660.find_record(a.tobytes(), args.path)
    lo = record.extent * BLOCK
    hi = lo + record.size
    print(f"   {args.path}: LBA {record.extent}, bytes 0x{lo:x}-0x{hi:x}")

    diff = np.flatnonzero(a != b)
    print(f"   {diff.size} differing bytes")
    outside = diff[(diff < lo) | (diff >= hi)]
    print(f"   {outside.size} of them fall OUTSIDE the file's extent")
    if outside.size:
        for off in outside[:12]:
            off = int(off)
            print(f"      0x{off:08x}: {a[off]:02x} -> {b[off]:02x}")
        print("   the patch touched something it should not have")
    else:
        print("   every change is inside the intended file; the ISO structure is intact")

    # the record itself must be untouched too
    rec = slice(record.offset, record.offset + 34)
    same = np.array_equal(a[rec], b[rec])
    print(f"   directory record at 0x{record.offset:x}: "
          f"{'unchanged' if same else 'MODIFIED'}")


if __name__ == "__main__":
    main()

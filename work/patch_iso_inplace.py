"""Write a replacement file into a copy of the ISO, in place.

The rebuilt archive keeps its original size, so the ISO directory records stay valid
and the payload can simply be overwritten at its existing LBA.  That is the safest
possible patch: no relocation, no directory edits, no volume-size change.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from iso9660 import BLOCK, find_record

ISO = Path(r"D:\psp\원격수사\Enkaku Sousa Shinjitsu eno 23nichikan.iso")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iso", type=Path, default=ISO)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--replace", action="append", nargs=2, metavar=("ISO_PATH", "FILE"),
                        required=True, help="e.g. --replace /PSP_GAME/USRDIR/0000 build/0000")
    args = parser.parse_args()

    if args.out.resolve() == args.iso.resolve():
        raise SystemExit("output must be a different file from the source ISO")

    iso = args.iso.read_bytes()
    plan = []
    for iso_path, file_path in args.replace:
        record = find_record(iso, iso_path)
        payload = Path(file_path).read_bytes()
        if len(payload) != record.size:
            raise SystemExit(
                f"{iso_path}: replacement is {len(payload)} bytes but the record says "
                f"{record.size}; in-place patching needs an exact size match")
        plan.append((iso_path, record, payload))
        print(f"{iso_path}: LBA {record.extent}, {record.size} bytes -> {file_path}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.iso, args.out)
    with args.out.open("r+b") as fh:
        for _, record, payload in plan:
            fh.seek(record.extent * BLOCK)
            fh.write(payload)

    written = args.out.read_bytes()
    for iso_path, record, payload in plan:
        start = record.extent * BLOCK
        if written[start : start + len(payload)] != payload:
            raise SystemExit(f"verification failed for {iso_path}")
    if len(written) != len(iso):
        raise SystemExit("ISO size changed unexpectedly")

    changed = sum(1 for a, b in zip(written, iso) if a != b)
    print(f"\n-> {args.out}")
    print(f"   size unchanged ({len(written)} bytes), {changed} bytes differ from the original")


if __name__ == "__main__":
    main()

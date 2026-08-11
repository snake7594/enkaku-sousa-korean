"""Try to reproduce the 16-byte stream header as an MD5 over some region.

BOOT.BIN does contain a real MD5 implementation (the T table sits at 0xE3DA4), so the
header being a digest is plausible.  The question is what it covers, hence this sweep
over plausible region boundaries and paddings.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import lzss

ROOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", default="0003")
    parser.add_argument("--block", type=lambda v: int(v, 0), default=0x0)
    args = parser.parse_args()

    data = (ROOT / args.archive).read_bytes()
    target = bytes(data[args.block : args.block + 16])
    print(f"{args.archive} block 0x{args.block:x} header {target.hex()}")

    stream_at = args.block + 0x40
    plain, consumed = lzss.decompress(data, stream_at)
    end_aligned = stream_at + ((consumed + 0x7FF) // 0x800) * 0x800
    print(f"stream packed 0x{consumed:x} plain 0x{len(plain):x}")

    zeroed = bytearray(data[args.block : end_aligned])
    zeroed[:16] = b"\0" * 16

    regions = {
        "packed": data[stream_at : stream_at + consumed],
        "packed + pad to 0x800": data[stream_at : end_aligned],
        "block incl header": data[args.block : end_aligned],
        "block, header zeroed": bytes(zeroed),
        "header+0x10 .. end": data[args.block + 0x10 : end_aligned],
        "0x40 header + packed": data[args.block : stream_at + consumed],
        "plain": plain,
        "plain padded 0x800": plain + b"\0" * ((-len(plain)) % 0x800),
        "whole file": data,
        "file after 0x40": data[0x40:],
    }
    for label, payload in regions.items():
        if hashlib.md5(payload).digest() == target:
            print(f"MATCH: md5 of {label}")
            return
    print("no match among the tried regions")

    occurrences = []
    start = 0
    while True:
        idx = data.find(target, start)
        if idx < 0:
            break
        occurrences.append(idx)
        start = idx + 1
        if len(occurrences) > 4:
            break
    print(f"header value occurs at: {[hex(o) for o in occurrences]}")


if __name__ == "__main__":
    main()

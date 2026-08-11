"""Identify the 16-byte header that precedes each compressed stream.

Each stream sits at a 0x800-aligned offset plus 0x40, and the first 16 bytes of that
block look random.  If they are a digest of the payload, repacking has to recompute
them; if not, they can be left alone.  This tries the usual candidates against a real
stream.
"""

from __future__ import annotations

import argparse
import hashlib
import zlib
from pathlib import Path

import lzss

ROOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR")


def digests(payload: bytes) -> dict[str, bytes]:
    out = {
        "md5": hashlib.md5(payload).digest(),
        "sha1[:16]": hashlib.sha1(payload).digest()[:16],
        "sha256[:16]": hashlib.sha256(payload).digest()[:16],
        "md5(4byte-crc)": zlib.crc32(payload).to_bytes(4, "little") * 4,
    }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", default="0003", nargs="?")
    parser.add_argument("--block", type=lambda v: int(v, 0), default=0x0)
    args = parser.parse_args()

    data = (ROOT / args.archive).read_bytes()
    header = data[args.block : args.block + 0x40]
    print(f"{args.archive} block 0x{args.block:x}")
    print("   header:", " ".join(f"{b:02x}" for b in header[:16]))
    print("   rest of 0x40 all zero:", not any(header[16:]))

    stream_at = args.block + 0x40
    plain, consumed = lzss.decompress(data, stream_at)
    packed = data[stream_at : stream_at + consumed]
    print(f"   stream: packed 0x{consumed:x}, plain 0x{len(plain):x}")

    target = bytes(header[:16])
    candidates = {
        "packed stream": packed,
        "packed, padded to 0x800": data[stream_at : stream_at + ((consumed + 0x7FF) // 0x800) * 0x800],
        "decompressed": plain,
    }
    for label, payload in candidates.items():
        for name, value in digests(payload).items():
            if value == target:
                print(f"   MATCH: {name} of {label}")
                return
    print("   no digest matched -> the 16 bytes are not a checksum of the payload")

    # is it perhaps constant per archive, or an index?
    others = []
    for index in range(1, 6):
        off = args.block + index * 0x800
        if off + 16 <= len(data):
            others.append(data[off : off + 16])
    print("   next blocks' first 16 bytes:")
    for chunk in others:
        print("      " + " ".join(f"{b:02x}" for b in chunk))


if __name__ == "__main__":
    main()

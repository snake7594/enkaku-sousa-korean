"""What is the sixteen bytes at the head of every block?

If it is a checksum over the payload, rewriting a picture means recomputing it, and getting
that wrong is the difference between a patch that boots and one that does not.  The 0000
archive has no such header, so nothing learned there applies.

Every plausible digest is tried over every plausible extent -- the packed stream, the block's
whole payload span, the decompressed contents -- and matches are counted.  If nothing matches,
the bytes are an identifier rather than a checksum and can be left alone.
"""

from __future__ import annotations

import argparse
import hashlib
import zlib
from pathlib import Path

import read_blocks

BLOCK = read_blocks.BLOCK
HEADER = read_blocks.HEADER


def candidates(blob: bytes, at: int, packed_end: int, plain: bytes | None):
    """Byte ranges the hash might cover."""
    payload = at + HEADER
    span_end = ((packed_end + BLOCK - 1) // BLOCK) * BLOCK
    yield "packed", blob[payload:packed_end]
    yield "padded span", blob[payload:span_end]
    if plain is not None:
        yield "decompressed", plain


def digests(data: bytes):
    yield "md5", hashlib.md5(data).digest()
    yield "sha1[:16]", hashlib.sha1(data).digest()[:16]
    yield "crc32", zlib.crc32(data).to_bytes(4, "little") + bytes(12)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="0001")
    parser.add_argument("--blocks", type=int, default=6)
    args = parser.parse_args()

    blob = (read_blocks.ROOT / args.name).read_bytes()
    hits: dict[str, int] = {}
    checked = 0
    for at, payload in read_blocks.blocks(blob):
        if checked >= args.blocks:
            break
        stored = blob[at:at + 0x10]
        plain = None
        packed_end = at + HEADER
        if payload[:1] == b"\x11":
            import lzss
            try:
                plain, consumed = lzss.decompress(payload, 0, limit=64 << 20)
                packed_end = at + HEADER + consumed
            except Exception:
                plain = None
        checked += 1
        print(f"  block {at:#09x}  stored {stored.hex()}")
        for where, data in candidates(blob, at, packed_end, plain):
            for how, value in digests(data):
                if value == stored or value[:4] == stored[:4]:
                    key = f"{how} over {where}"
                    hits[key] = hits.get(key, 0) + 1
                    print(f"     MATCH {key}")
    print(f"\n{checked} blocks checked")
    print("matches:", hits or "none -- the sixteen bytes are not a digest of the payload")


if __name__ == "__main__":
    main()

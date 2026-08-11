"""Block header handling for the USRDIR archives.

Layout of one block:

    +0x00  16 bytes  MD5 of the payload region below
    +0x10  0x30      zero padding
    +0x40  ...       LZ11 stream, zero-padded out to the next block

The digest covers everything from +0x40 up to the start of the next block (or the end
of the file), padding included — so repacking must recompute it after the padding is
in place, not before.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import lzss

ROOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR")
ALIGN = 0x800
HEADER = 0x40


def block_size_for(packed_len: int) -> int:
    """A block is its 0x40 header plus the stream, rounded up to the 0x800 grid."""
    return ((HEADER + packed_len + ALIGN - 1) // ALIGN) * ALIGN


def walk_blocks(data: bytes, first: int = 0) -> list[tuple[int, int, int]]:
    """Sequential walk: (base, packed length, block size).

    Scanning every 0x800 offset for an LZ11 magic finds false positives inside a
    stream's own data, which then truncate the previous block's span.  Walking
    block-to-block instead gives exact boundaries.
    """
    blocks = []
    base = first
    while base + HEADER + 8 <= len(data):
        result = lzss.try_decompress(data, base + HEADER, limit=0x4000000)
        if result is None:
            break
        _, consumed = result
        size = block_size_for(consumed)
        blocks.append((base, consumed, size))
        base += size
    return blocks


def payload_span(base: int, size: int) -> tuple[int, int]:
    return base + HEADER, base + size


def block_digest(payload: bytes) -> bytes:
    return hashlib.md5(payload).digest()


def build_block(stream: bytes, block_size: int | None = None) -> bytes:
    """Assemble one block: header + padding + stream, padded to `block_size`."""
    body = bytearray(stream)
    if block_size is None:
        block_size = HEADER + ((len(body) + ALIGN - 1) // ALIGN) * ALIGN
    pad = block_size - HEADER - len(body)
    if pad < 0:
        raise ValueError("stream does not fit the requested block size")
    body += b"\0" * pad
    return block_digest(bytes(body)) + b"\0" * (HEADER - 16) + bytes(body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+")
    args = parser.parse_args()

    for name in args.archives:
        data = (ROOT / name).read_bytes()
        first = 0x800 if data[HEADER] != 0x11 else 0
        blocks = walk_blocks(data, first)
        ok = bad = 0
        first_bad = None
        for base, _, size in blocks:
            start, end = payload_span(base, size)
            if block_digest(data[start:end]) == data[base : base + 16]:
                ok += 1
            else:
                bad += 1
                if first_bad is None:
                    first_bad = (base, start, end)
        covered = blocks[-1][0] + blocks[-1][2] if blocks else first
        print(f"{name}: {len(blocks)} blocks, header MD5 verified {ok}, mismatched {bad}; "
              f"walked to 0x{covered:x} of 0x{len(data):x}")
        if first_bad:
            print(f"   first mismatch at block 0x{first_bad[0]:x} "
                  f"(payload 0x{first_bad[1]:x}-0x{first_bad[2]:x})")


if __name__ == "__main__":
    main()

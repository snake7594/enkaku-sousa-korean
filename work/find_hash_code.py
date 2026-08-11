"""Look for hash/CRC implementations in BOOT.BIN.

If the 16 bytes in front of each stream were a digest the game verifies, the
executable would have to contain the algorithm — and every common one is recognisable
from its initialisation constants or lookup table.  Absence of all of them is good
evidence the field is not checked at load time.
"""

from __future__ import annotations

import argparse
from pathlib import Path

SIGNATURES: dict[str, list[int]] = {
    "MD5 init":      [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476],
    "SHA1 init":     [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0],
    "SHA256 init":   [0x6A09E667, 0xBB67AE85, 0x3C6EF372, 0xA54FF53A],
    "CRC32 poly":    [0xEDB88320],
    "CRC32 poly BE": [0x04C11DB7],
    "MD5 T[0]":      [0xD76AA478],
    "SHA256 K[0]":   [0x428A2F98],
    "Adler/zlib":    [0xFFF1],
}


def find_u32(data: bytes, value: int) -> list[int]:
    hits = []
    for endian in ("little", "big"):
        needle = value.to_bytes(4, endian)
        start = 0
        while True:
            idx = data.find(needle, start)
            if idx < 0:
                break
            hits.append(idx)
            start = idx + 1
    return hits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    data = args.path.read_bytes()
    print(f"{args.path.name}: {len(data)} bytes\n")
    for name, values in SIGNATURES.items():
        found = {v: find_u32(data, v) for v in values}
        present = [v for v, hits in found.items() if hits]
        if len(present) == len(values):
            spots = ", ".join(f"0x{found[v][0]:x}" for v in values)
            print(f"   FOUND  {name:14s} all constants present at {spots}")
        elif present:
            print(f"   partial {name:14s} {len(present)}/{len(values)} constants "
                  f"(likely coincidence in MIPS immediates)")
        else:
            print(f"   absent {name}")


if __name__ == "__main__":
    main()

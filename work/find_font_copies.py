"""Search the decompressed archives for a second copy of the glyph table.

The ISO holds no uncompressed copy, so if the game is reading glyphs the patch did not
touch, the other copy must live inside some compressed stream.  A distinctive run of
glyph tiles is used as the probe.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import lzss

ROOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR")
DUMP = Path(r"D:\psp\원격수사\dump")
STREAM1 = 0x27E000
FONT_OFFSET = 0x80


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tile", type=int, default=674, help="tile index used as the probe")
    parser.add_argument("--tiles", type=int, default=4)
    args = parser.parse_args()

    archive = (ROOT / "0000").read_bytes()
    plain1, _ = lzss.decompress(archive, STREAM1)
    start = FONT_OFFSET + args.tile * 256
    probe = plain1[start : start + args.tiles * 256]
    print(f"probe: {len(probe)} bytes from tile {args.tile} (glyphs {args.tile * 2}..)")

    def scan(name: str, blob: bytes) -> None:
        hits, pos = [], 0
        while len(hits) < 5:
            idx = blob.find(probe, pos)
            if idx < 0:
                break
            hits.append(idx)
            pos = idx + 1
        if hits:
            print(f"   {name}: found at {[hex(h) for h in hits]}")

    print("\nsearching decompressed streams ...")
    plain0, _ = lzss.decompress(archive, 0)
    scan("0000 stream0", plain0)
    scan("0000 stream1", plain1)
    scan("BOOT.BIN", (ROOT.parent / "SYSDIR" / "BOOT.BIN").read_bytes())

    for folder in sorted(DUMP.glob("00*")):
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.bin")):
            scan(f"{folder.name}/{path.name}", path.read_bytes())
    print("done")


if __name__ == "__main__":
    main()

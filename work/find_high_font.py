"""Search for a second copy of the *high* part of the glyph table.

Slots 107, 108 and 200 took the patch; 400 and above kept their original bitmaps.
That boundary sits at 256 — the width of one lead byte — so the table the game loads
is probably only the first block, with the rest coming from somewhere the patch did
not touch.  The earlier duplicate search used glyph 107 as its probe, which lives in
the block that *does* work, so it could never have found the other copy.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import lzss

ROOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR")
DUMP = Path(r"D:\psp\원격수사\dump")
ISO = Path(r"D:\psp\원격수사\Enkaku Sousa Shinjitsu eno 23nichikan.iso")
STREAM1 = 0x27E000
FONT_OFFSET = 0x80


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--glyph", type=int, default=400)
    parser.add_argument("--tiles", type=int, default=4)
    args = parser.parse_args()

    archive = (ROOT / "0000").read_bytes()
    plain1, _ = lzss.decompress(archive, STREAM1)
    tile = args.glyph // 2
    start = FONT_OFFSET + tile * 256
    probe = plain1[start : start + args.tiles * 256]
    print(f"probe: glyph {args.glyph} (tile {tile}), {len(probe)} bytes from 0x{start:x}")

    targets: list[tuple[str, bytes]] = [
        ("0000 stream1 (the copy we patch)", plain1),
        ("0000 stream0", lzss.decompress(archive, 0)[0]),
        ("BOOT.BIN", (ROOT.parent / "SYSDIR" / "BOOT.BIN").read_bytes()),
        ("raw ISO", ISO.read_bytes()),
    ]
    for folder in sorted(DUMP.glob("00*")):
        if folder.is_dir():
            for path in sorted(folder.glob("*.bin")):
                targets.append((f"{folder.name}/{path.name}", path.read_bytes()))

    total = 0
    for name, blob in targets:
        hits, pos = [], 0
        while len(hits) < 4:
            idx = blob.find(probe, pos)
            if idx < 0:
                break
            hits.append(idx)
            pos = idx + 1
        if hits:
            total += len(hits)
            print(f"   {name}: {[hex(h) for h in hits]}")
    print(f"\n{total} hit(s) total")


if __name__ == "__main__":
    main()

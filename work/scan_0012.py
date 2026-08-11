"""Search the 404 MB archive for the title-menu textures.

0001-0023 came back with no texture streams, and 0012 was skipped as too large for that
pass.  It is the last place in USRDIR the title menu could be, so it gets scanned properly:
0x800-aligned candidates, LZ11 magic, and the record-table reader applied to whatever
decompresses.

Reported by size group rather than by count -- the title menu items are short labels, so a
stream holding a run of small textures is the thing to look for.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import lzss
import texpack

ROOT = Path(r"D:\psp\원격수사")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path,
                        default=ROOT / "iso_extract" / "PSP_GAME" / "USRDIR" / "0012")
    parser.add_argument("--step", type=int, default=0x800)
    parser.add_argument("--report-every", type=int, default=40_000_000)
    args = parser.parse_args()

    data = args.file.read_bytes()
    print(f"{args.file.name}: {len(data)} bytes, scanning every 0x{args.step:x}")

    hits, checked, next_report = [], 0, args.report_every
    for off in range(0, len(data) - 8, args.step):
        if data[off] != 0x11:
            continue
        checked += 1
        try:
            plain, packed = lzss.decompress(data, off)
        except Exception:
            continue
        if len(plain) < 0x400:
            continue
        try:
            textures = texpack.load_textures(plain)
        except Exception:
            continue
        if textures:
            sizes = Counter((t.width, t.height) for t in textures)
            hits.append((off, len(plain), len(textures), sizes))
            print(f"   @0x{off:08x}  {len(plain)} bytes, {len(textures)} textures  "
                  f"{sizes.most_common(5)}")
        if off >= next_report:
            print(f"   ... {off / len(data) * 100:.0f}% scanned, "
                  f"{checked} candidates tried, {len(hits)} streams found")
            next_report += args.report_every

    print(f"\n{checked} LZ11 candidates tried, {len(hits)} texture streams found")
    if not hits:
        print("   the title menu is not in a texture stream in this file")


if __name__ == "__main__":
    main()

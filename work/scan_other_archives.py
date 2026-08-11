"""Look for the title-menu textures in the archives other than 0000.

最初から / 続きから / データインストール / 設定 and the START line are not in 0000, so they
live somewhere else.  The other USRDIR files may or may not use the same container; this
tries the same LZ11 + record-table reading on each and reports what comes back rather than
assuming they match.

Nothing is written.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import lzss
import texpack

ROOT = Path(r"D:\psp\원격수사")
USRDIR = ROOT / "iso_extract" / "PSP_GAME" / "USRDIR"


def try_stream(data: bytes, offset: int):
    try:
        plain, packed = lzss.decompress(data, offset)
    except Exception:
        return None
    if len(plain) < 0x100:
        return None
    return plain, packed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-size", type=int, default=45_000_000)
    args = parser.parse_args()

    for path in sorted(USRDIR.iterdir()):
        if not path.is_file() or path.name == "0000":
            continue
        size = path.stat().st_size
        if size > args.max_size:
            print(f"{path.name}: {size} bytes -- skipped (too large for this pass)")
            continue
        data = path.read_bytes()
        found = []
        # LZ11 streams start with 0x11 and sit at 0x800-aligned offsets in 0000;
        # scan the same way rather than assuming a single layout
        for off in range(0, min(len(data), 0x400000), 0x800):
            if data[off] != 0x11:
                continue
            got = try_stream(data, off)
            if got is None:
                continue
            plain, packed = got
            try:
                textures = texpack.load_textures(plain)
            except Exception:
                textures = []
            if textures:
                sizes = Counter((t.width, t.height) for t in textures)
                found.append((off, len(plain), len(textures), sizes.most_common(4)))
        if found:
            print(f"\n{path.name}: {size} bytes")
            for off, plain_len, count, sizes in found[:6]:
                print(f"   stream @0x{off:06x} -> {plain_len} bytes, "
                      f"{count} textures {sizes}")
        else:
            print(f"{path.name}: {size} bytes -- no texture streams found")


if __name__ == "__main__":
    main()

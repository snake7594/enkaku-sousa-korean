"""Second search for a duplicate glyph table, this time layout-agnostic.

The first search used the paired 32x16 tile bytes as the probe.  A copy stored as
plain consecutive 16x16 glyphs would have a completely different byte order and be
missed, so this looks for one distinctive glyph laid out contiguously — both as 4bpp
rows and as the row-reversed and nibble-swapped variants a different packer might use.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

import font as fontlib
import lzss

ROOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR")
DUMP = Path(r"D:\psp\원격수사\dump")
ISO = Path(r"D:\psp\원격수사\Enkaku Sousa Shinjitsu eno 23nichikan.iso")
STREAM1 = 0x27E000
FONT_OFFSET = 0x80
FONT_TILES = 684


def variants(glyph: np.ndarray) -> dict[str, bytes]:
    """4bpp packings a different tool might have produced for one 16x16 glyph."""
    hi_first = ((glyph[:, 0::2] << 4) | glyph[:, 1::2]).astype(np.uint8).tobytes()
    lo_first = ((glyph[:, 1::2] << 4) | glyph[:, 0::2]).astype(np.uint8).tobytes()
    inverted = (((15 - glyph)[:, 0::2] << 4) | (15 - glyph)[:, 1::2]).astype(np.uint8).tobytes()
    one_bpp = np.packbits((glyph > 7).astype(np.uint8), axis=1).tobytes()
    eight_bpp = (glyph * 17).astype(np.uint8).tobytes()
    return {"4bpp": hi_first, "4bpp swapped": lo_first, "4bpp inverted": inverted,
            "1bpp": one_bpp, "8bpp": eight_bpp}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--glyph", type=int, default=107)
    args = parser.parse_args()

    archive = (ROOT / "0000").read_bytes()
    plain1, _ = lzss.decompress(archive, STREAM1)
    glyphs = fontlib.tiles_to_glyphs(plain1, FONT_OFFSET, FONT_TILES)
    probes = variants(glyphs[args.glyph])
    print(f"probing with glyph {args.glyph}, {len(probes)} packings "
          f"({', '.join(f'{k}:{len(v)}B' for k, v in probes.items())})")

    haystacks: list[tuple[str, bytes]] = [
        ("0000 stream1", plain1),
        ("0000 stream0", lzss.decompress(archive, 0)[0]),
        ("BOOT.BIN", (ROOT.parent / "SYSDIR" / "BOOT.BIN").read_bytes()),
        ("whole ISO", ISO.read_bytes()),
    ]
    for folder in sorted(DUMP.glob("00*")):
        if folder.is_dir():
            for path in sorted(folder.glob("*.bin")):
                haystacks.append((f"{folder.name}/{path.name}", path.read_bytes()))

    found = False
    for name, blob in haystacks:
        for label, probe in probes.items():
            idx = blob.find(probe)
            if idx >= 0:
                print(f"   {name}: {label} at 0x{idx:x}")
                found = True
    if not found:
        print("   no copy found in any packing")


if __name__ == "__main__":
    main()

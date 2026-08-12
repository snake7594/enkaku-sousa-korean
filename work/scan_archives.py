"""Look for the same archive layout in the other USRDIR files that 0000 uses.

0000 is not a container with an index.  Its streams sit raw at 0x800-aligned offsets, each one
beginning with an LZ11 header -- byte 0x11 followed by a 24-bit little-endian decompressed
size -- and nothing announces where they are.  Every earlier search for the title menu treated
the other numbered files as opaque, which only meant nobody had tried the one layout the game
is known to use.

Their entropy says the question is open: 0001 through 0004 and 0011 sit at 7.5 to 7.8, the
same range as 0000, while 0010, 0012, 0013 and the video files sit at 7.8 to 8.0 like
encrypted or already-compressed data.

So this walks each file at 0x800 and reports every offset that decompresses.  A file that
yields nothing is genuinely not this format; a file that yields streams can then be checked
for a texture table.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import lzss

ROOT = Path(r"D:\psp\원격수사")
ISO = ROOT / "iso_extract" / "PSP_GAME" / "USRDIR"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", nargs="*", default=["0001", "0002", "0003", "0004", "0011"])
    parser.add_argument("--align", type=lambda v: int(v, 0), default=0x800)
    parser.add_argument("--min-size", type=int, default=4096)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "archive_scan.json")
    args = parser.parse_args()

    found = {}
    for name in args.files:
        path = ISO / name
        if not path.exists():
            print(f"{name}: missing")
            continue
        blob = path.read_bytes()
        streams = []
        for offset in range(0, len(blob) - 4, args.align):
            if blob[offset] != 0x11:
                continue
            size = int.from_bytes(blob[offset + 1:offset + 4], "little")
            if not (args.min_size <= size <= 64 << 20):
                continue
            try:
                plain, consumed = lzss.decompress(blob, offset, limit=64 << 20)
            except Exception:
                continue
            if len(plain) != size:
                continue
            streams.append({"offset": offset, "compressed_bytes": consumed,
                            "decompressed": len(plain),
                            "head": plain[:16].hex()})
        found[name] = {"size": len(blob), "streams": streams}
        print(f"{name}: {len(blob):>10d} bytes, {len(streams)} LZ11 streams at {args.align:#x}")
        for s in streams[:6]:
            print(f"   {s['offset']:#010x} -> {s['decompressed']:>9d}  {s['head']}")

    args.out.write_text(json.dumps({"schema": "enkaku_archive_scan_v1", "files": found},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

"""Pull the textures out of 0001-0004, which earlier scans said held none.

They do.  The scan that cleared them only looked at 0x800 boundaries, because that is where
0000 keeps its two streams, and these files put theirs at 0x40 past each 0x800 -- so every
probe landed forty bytes short of a header and every file came back empty.  Fixing the stride
turns up 276 streams in 0001, 568 in 0002, 126 in 0003 and 9 in 0004, and their first bytes
are a table of u32 offsets, the same shape as the texture container in stream0.

That matters because the title menu has never been found.  It is not a Shift-JIS string, not
in the script, and not addressable in the script font, and this is the first place left that
was ruled out by a bad measurement rather than by evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import lzss
import texpack

ROOT = Path(r"D:\psp\원격수사")
ISO = ROOT / "iso_extract" / "PSP_GAME" / "USRDIR"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", nargs="*", default=["0001", "0002", "0003", "0004"])
    parser.add_argument("--align", type=lambda v: int(v, 0), default=0x10)
    parser.add_argument("--min-size", type=int, default=16384)
    parser.add_argument("--limit", type=int, default=40, help="streams to open per file")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "other_archives.json")
    args = parser.parse_args()

    summary = {}
    for name in args.files:
        blob = (ISO / name).read_bytes()
        streams, offset = [], 0
        while offset < len(blob) - 4 and len(streams) < args.limit:
            if blob[offset] == 0x11:
                size = int.from_bytes(blob[offset + 1:offset + 4], "little")
                if args.min_size <= size <= 64 << 20:
                    try:
                        plain, consumed = lzss.decompress(blob, offset, limit=64 << 20)
                    except Exception:
                        plain = None
                    if plain is not None and len(plain) == size:
                        try:
                            textures = list(texpack.load_textures(plain))
                        except Exception:
                            textures = []
                        streams.append({"offset": offset, "size": size,
                                        "textures": len(textures),
                                        "sizes": sorted({(t.width, t.height)
                                                         for t in textures})[:6]})
                        offset += max(consumed, args.align)
                        continue
            offset += args.align
        summary[name] = streams
        total = sum(s["textures"] for s in streams)
        print(f"{name}: {len(streams)} streams opened, {total} textures")
        for s in streams[:6]:
            print(f"   {s['offset']:#010x}  {s['size']:>8d} bytes  "
                  f"{s['textures']:3d} textures  {s['sizes']}")

    args.out.write_text(json.dumps({"schema": "enkaku_other_archives_v1",
                                    "files": summary}, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

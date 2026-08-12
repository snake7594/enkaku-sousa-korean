"""Decode the textures in 0001-0003, which use the same container as stream0 with one change.

stream0's record 0 opens with the offset of its size table, so texpack reads start from word 0
and end from word 1.  These archives put a zero there and the table begins one word later, so
the same reader finds a count of eight and then parses the header as if it were dimensions,
which is why every texture came out 0x0 and the files were written off as holding none.

Reading start from word 1 instead gives sensible sizes.  Everything after that -- palette in
record i*2+1, image in record i*2+2, 4bpp or 8bpp, block swizzle -- is unchanged, so texpack
does the rest.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import lzss
import texpack

ROOT = Path(r"D:\psp\원격수사")
ISO = ROOT / "iso_extract" / "PSP_GAME" / "USRDIR"
LABEL = Path(r"C:\Windows\Fonts\consola.ttf")


def load(plain: bytes):
    records = texpack.load_records(plain)
    meta = records[0]
    start, end = struct.unpack_from("<II", meta, 4)
    count = max(0, (end - start) // 8)
    out = []
    for i in range(count):
        if start + i * 8 + 8 > len(meta) or i * 2 + 2 >= len(records):
            break
        width, height, psm = struct.unpack_from("<HHI", meta, start + i * 8)
        if not (0 < width <= 1024 and 0 < height <= 1024):
            continue
        out.append(texpack.Texture(i, width, height, psm,
                                   records[i * 2 + 1], records[i * 2 + 2]))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", nargs="*", default=["0001", "0002", "0003"])
    parser.add_argument("--align", type=lambda v: int(v, 0), default=0x10)
    parser.add_argument("--max-streams", type=int, default=24)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "build" / "other_tex")
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "other_tex.json")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary = {}
    for name in args.files:
        blob = (ISO / name).read_bytes()
        found, offset, opened = [], 0, 0
        while offset < len(blob) - 4 and opened < args.max_streams:
            if blob[offset] == 0x11:
                size = int.from_bytes(blob[offset + 1:offset + 4], "little")
                if 16384 <= size <= 64 << 20:
                    try:
                        plain, consumed = lzss.decompress(blob, offset, limit=64 << 20)
                    except Exception:
                        plain = None
                    if plain is not None and len(plain) == size:
                        opened += 1
                        for tex in load(plain):
                            image = texpack.decode(tex)
                            if image is None:
                                continue
                            key = f"{name}_{offset:08x}_{tex.index:03d}"
                            image.convert("RGBA").save(args.out_dir / f"{key}.png")
                            found.append({"stream": offset, "index": tex.index,
                                          "size": [tex.width, tex.height], "psm": tex.psm})
                        offset += max(consumed, args.align)
                        continue
            offset += args.align
        summary[name] = found
        sizes = sorted({tuple(f["size"]) for f in found})
        print(f"{name}: {opened} streams, {len(found)} textures decoded, sizes {sizes[:10]}")

    args.report.write_text(json.dumps({"schema": "enkaku_other_tex_v1", "files": summary},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {args.out_dir}\n-> {args.report}")


if __name__ == "__main__":
    main()

"""Dump every LZ11 stream out of a USRDIR archive, then split each stream by its
leading 32-bit offset table into individual records."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

import lzss

ROOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR")
OUT = Path(r"D:\psp\원격수사\dump")


def find_streams(data: bytes, align: int = 0x800) -> list[int]:
    """Offsets of LZ11 streams: archives place them at 0x800-aligned +0x40 (or +0x00)."""
    offsets = []
    for base in range(0, len(data) - 8, align):
        for delta in (0x00, 0x40):
            pos = base + delta
            if pos + 8 > len(data) or data[pos] != 0x11:
                continue
            declared = int.from_bytes(data[pos + 1 : pos + 4], "little")
            if 0x100 <= declared <= 0x4000000:
                offsets.append(pos)
                break
    return offsets


def split_records(plain: bytes) -> list[tuple[int, int]] | None:
    """A stream begins with a table of absolute u32 offsets; entry 0 is the table size."""
    if len(plain) < 8:
        return None
    first = struct.unpack_from("<I", plain, 0)[0]
    if first < 8 or first > len(plain) or first % 4:
        return None
    count = first // 4
    offsets = list(struct.unpack_from(f"<{count}I", plain, 0))
    if any(o > len(plain) for o in offsets):
        return None
    if offsets != sorted(offsets):
        return None
    bounds = offsets + [len(plain)]
    return [(bounds[i], bounds[i + 1]) for i in range(count)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="+")
    parser.add_argument("--split", action="store_true", help="also split streams into records")
    args = parser.parse_args()

    for name in args.names:
        data = (ROOT / name).read_bytes()
        out_dir = OUT / name
        out_dir.mkdir(parents=True, exist_ok=True)
        offsets = find_streams(data)
        print(f"== {name}: {len(offsets)} candidate streams")
        kept = 0
        for index, pos in enumerate(offsets):
            result = lzss.try_decompress(data, pos, limit=0x4000000)
            if result is None:
                print(f"   !! stream {index} @0x{pos:x} failed to decompress")
                continue
            plain, _ = result
            stem = f"{index:04d}_{pos:08x}"
            (out_dir / f"{stem}.bin").write_bytes(plain)
            kept += 1
            if args.split:
                records = split_records(plain)
                if records:
                    rec_dir = out_dir / stem
                    rec_dir.mkdir(exist_ok=True)
                    for ri, (start, end) in enumerate(records):
                        (rec_dir / f"r{ri:04d}.bin").write_bytes(plain[start:end])
        print(f"   decompressed {kept} streams -> {out_dir}")


if __name__ == "__main__":
    main()

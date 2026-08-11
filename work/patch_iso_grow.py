"""Replace a file inside a PSP ISO with a larger one, by relocating it into free space.

The in-place patcher only handles same-size replacements, because a file that grows past
its neighbour would overwrite it.  This one moves the file instead.

The image has room: 38,604 sectors (79 MB) sit unused after /PSP_GAME/SYSDIR/UPDATE/DATA.BIN
and every byte of them is zero -- checked, not assumed.  Relocating into a gap *inside* the
image means the ISO keeps its size and the primary volume descriptor's volume space stays
correct, so the only thing that changes is the file's own directory record.

Two details matter and both are easy to get wrong:

  * ISO9660 stores extent and size twice, little-endian then big-endian.  A reader that
    consults the big-endian copy sees a stale value if only the first is updated, and the
    failure looks like random corruption rather than a bad patch.
  * the old extent is left alone.  Blanking it would be tidier but risks clobbering data
    some other record shares, and dead sectors cost nothing.

Nothing is written without --write; the default is a dry run.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

import iso9660

BLOCK = 2048


def sectors(size: int) -> int:
    return (size + BLOCK - 1) // BLOCK


def free_gaps(iso: bytes) -> list[tuple[int, int]]:
    """Runs of sectors no file claims, in (start_lba, count) form, largest first."""
    files = sorted((r for r in iso9660.list_records(iso) if not (r.flags & 2)),
                   key=lambda r: r.extent)
    gaps = []
    for a, b in zip(files, files[1:]):
        end = a.extent + sectors(a.size)
        if b.extent > end:
            gaps.append((end, b.extent - end))
    last = files[-1]
    tail = len(iso) // BLOCK - (last.extent + sectors(last.size))
    if tail > 0:
        gaps.append((last.extent + sectors(last.size), tail))
    gaps.sort(key=lambda g: -g[1])
    return gaps


def pick_gap(iso: bytes, gaps: list, need: int) -> tuple[int, int]:
    """The largest gap that fits and is genuinely empty."""
    for lba, count in gaps:
        if count < need:
            continue
        chunk = iso[lba * BLOCK:(lba + count) * BLOCK]
        if any(chunk):
            print(f"   gap at LBA {lba} ({count} sectors) is not empty; skipping")
            continue
        return lba, count
    raise SystemExit(f"no empty gap holds {need} sectors")


def patch_record(iso: bytearray, offset: int, extent: int, size: int) -> None:
    """Write both-endian extent and size into a directory record."""
    struct.pack_into("<I", iso, offset + 2, extent)
    struct.pack_into(">I", iso, offset + 6, extent)
    struct.pack_into("<I", iso, offset + 10, size)
    struct.pack_into(">I", iso, offset + 14, size)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iso", type=Path, required=True)
    parser.add_argument("--path", default="/PSP_GAME/USRDIR/0000")
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--write", action="store_true", help="actually produce the ISO")
    args = parser.parse_args()

    iso = bytearray(args.iso.read_bytes())
    payload = args.data.read_bytes()
    record = iso9660.find_record(bytes(iso), args.path)
    print(f"{args.iso.name}: {len(iso)} bytes, {len(iso) // BLOCK} sectors")
    print(f"{args.path}: LBA {record.extent}, {record.size} bytes, "
          f"record at 0x{record.offset:x}")
    print(f"replacement: {len(payload)} bytes ({len(payload) - record.size:+d})")

    if len(payload) <= record.size:
        print("\nthe replacement is not larger; the in-place patcher is the right tool")

    need = sectors(len(payload))
    gaps = free_gaps(bytes(iso))
    print(f"\n{len(gaps)} gaps; largest: "
          f"{[(lba, count) for lba, count in gaps[:3]]}")
    lba, count = pick_gap(bytes(iso), gaps, need)
    print(f"   chosen: LBA {lba}, {count} sectors free, {need} needed "
          f"({count - need} left over)")

    if not args.write:
        print("\ndry run; pass --write to produce the ISO")
        return
    if not args.out:
        raise SystemExit("--write needs --out")

    iso[lba * BLOCK:lba * BLOCK + len(payload)] = payload
    pad = need * BLOCK - len(payload)
    if pad:
        iso[lba * BLOCK + len(payload):(lba + need) * BLOCK] = b"\x00" * pad
    patch_record(iso, record.offset, lba, len(payload))

    # read it back the way the console would, through the directory record
    check = iso9660.find_record(bytes(iso), args.path)
    start = check.extent * BLOCK
    ok = (check.extent == lba and check.size == len(payload)
          and bytes(iso[start:start + check.size]) == payload)
    print(f"\n   record now says LBA {check.extent}, {check.size} bytes")
    print(f"   {'OK  ' if ok else 'FAIL'} the file reads back byte-for-byte")
    others = [r for r in iso9660.list_records(bytes(iso))
              if not (r.flags & 2) and r.name.lower() != args.path.lower()
              and r.extent < lba + need and r.extent + sectors(r.size) > lba]
    print(f"   {'OK  ' if not others else 'FAIL'} no other file overlaps the new extent"
          + ("" if not others else f": {[r.name for r in others]}"))
    if not ok or others:
        raise SystemExit("verification failed; nothing written")

    args.out.write_bytes(bytes(iso))
    print(f"\n-> {args.out} ({len(iso)} bytes, unchanged size)")


if __name__ == "__main__":
    main()

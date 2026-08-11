"""Minimal ISO9660 reader for PSP ISOs (shared helper for the 원격수사 project)."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

BLOCK = 2048


@dataclass(frozen=True)
class DirectoryRecord:
    offset: int      # byte offset of the directory record inside the ISO
    name: str        # full path, e.g. /PSP_GAME/USRDIR/0000
    extent: int      # starting LBA
    size: int        # size in bytes
    flags: int


def read_both(data: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from("<I", data, offset)[0], struct.unpack_from(">I", data, offset + 4)[0]


def parse_record(data: bytes, offset: int) -> DirectoryRecord:
    length = data[offset]
    if length < 34 or offset + length > len(data):
        raise ValueError(f"invalid ISO directory record at 0x{offset:X}")
    extent_le, extent_be = read_both(data, offset + 2)
    size_le, size_be = read_both(data, offset + 10)
    if extent_le != extent_be or size_le != size_be:
        raise ValueError(f"mismatched ISO both-endian field at 0x{offset:X}")
    name_length = data[offset + 32]
    raw_name = data[offset + 33 : offset + 33 + name_length]
    name = raw_name.decode("ascii", "replace")
    if name.endswith(";1"):
        name = name[:-2]
    return DirectoryRecord(offset, name, extent_le, size_le, data[offset + 25])


def walk_directory(iso: bytes, extent: int, size: int, path: str, seen: set[tuple[int, int]]):
    key = (extent, size)
    if key in seen:
        return
    seen.add(key)
    start = extent * BLOCK
    directory = iso[start : start + size]
    pos = 0
    while pos < len(directory):
        if directory[pos] == 0:
            pos = ((pos // BLOCK) + 1) * BLOCK
            continue
        record = parse_record(directory, pos)
        absolute = start + pos
        if record.name not in ("\x00", "\x01"):
            full_path = f"{path}/{record.name}"
            yield DirectoryRecord(absolute, full_path, record.extent, record.size, record.flags)
            if record.flags & 2:
                yield from walk_directory(iso, record.extent, record.size, full_path, seen)
        pos += directory[pos]


def list_records(iso: bytes) -> list[DirectoryRecord]:
    pvd_offset = 16 * BLOCK
    if iso[pvd_offset + 1 : pvd_offset + 6] != b"CD001":
        raise ValueError("not an ISO9660 primary volume descriptor")
    root = parse_record(iso, pvd_offset + 156)
    return list(walk_directory(iso, root.extent, root.size, "", set()))


def find_record(iso: bytes, path: str) -> DirectoryRecord:
    wanted = path.lower()
    for record in list_records(iso):
        if record.name.lower() == wanted:
            return record
    raise FileNotFoundError(f"ISO directory record not found: {path}")


def read_file(iso_path: Path, record: DirectoryRecord) -> bytes:
    with open(iso_path, "rb") as handle:
        handle.seek(record.extent * BLOCK)
        return handle.read(record.size)

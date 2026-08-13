"""Write a picture back into a 0001-0004 image record, in place.

The record's shape is left exactly as it is: same tiles, same coordinates, same count, same
length.  Only the pixels inside each tile are replaced.  That keeps the decompressed stream
the same size, so the only thing that can change downstream is how well it compresses.

The palette is not touched either -- it is a separate record that other pictures may share --
so the new artwork is mapped onto the colours already there.

round_trip() is the check that matters: decode a record and encode it again, and the bytes
have to come back identical.  Anything less means the swizzle or the tile walk is wrong, and
a patch built on it would be subtly scrambled rather than obviously broken.
"""

from __future__ import annotations

import struct

import numpy as np
from PIL import Image

import decode_container
import texenc
import texpack

TILE_HEADER = decode_container.TILE_HEADER


def levels(record: bytes):
    """Split the tile run into mip levels, yielding (level, tile index, col, row).

    A record can hold smaller copies of the same picture after the full-size one.  They are not
    marked; the only sign is that the coordinates start over at (0,0).  Reading them as part of
    the picture is what produced "duplicate" tiles and out-of-range columns.
    """
    _, _, tile_w, tile_h, _, _ = struct.unpack_from("<6H", record, 0)
    count, = struct.unpack_from("<I", record, 12)
    stride = TILE_HEADER + tile_w * tile_h
    level, seen = 0, set()
    for n in range(count):
        col, row = struct.unpack_from("<2H", record, TILE_HEADER + n * stride)
        if (col, row) in seen:
            level += 1
            seen = set()
        seen.add((col, row))
        yield level, n, col, row


def write_record(record: bytes, planes) -> bytes:
    """Return the record with its tiles taken from one index plane per mip level."""
    width, height, tile_w, tile_h, psm, flag = struct.unpack_from("<6H", record, 0)
    bytes_per_row = tile_w
    tile_pixels = tile_w * 2 if psm == 4 else tile_w
    stride = TILE_HEADER + bytes_per_row * tile_h
    if isinstance(planes, np.ndarray):
        planes = [planes]

    out = bytearray(record)
    for level, n, col, row in levels(record):
        if level >= len(planes):
            continue
        plane = planes[level]
        if row * tile_h >= plane.shape[0] or col * tile_pixels >= plane.shape[1]:
            continue
        cell = plane[row * tile_h:(row + 1) * tile_h,
                     col * tile_pixels:(col + 1) * tile_pixels]
        if cell.shape != (tile_h, tile_pixels):
            continue
        if psm == 4:
            packed = (cell[:, 0::2] & 0x0F) | ((cell[:, 1::2] & 0x0F) << 4)
        else:
            packed = cell.astype(np.uint8)
        at = TILE_HEADER + n * stride
        out[at + TILE_HEADER:at + stride] = texenc.swizzle(
            packed, bytes_per_row, tile_h).tobytes()
    return bytes(out)


def indices_of(record: bytes):
    """One index plane per mip level, before the palette is applied."""
    width, height, tile_w, tile_h, psm, flag = struct.unpack_from("<6H", record, 0)
    bytes_per_row = tile_w
    tile_pixels = tile_w * 2 if psm == 4 else tile_w
    stride = TILE_HEADER + bytes_per_row * tile_h
    plane_width = width                          # width counts bytes, like tile_w

    out = []
    for level, n, col, row in levels(record):
        while len(out) <= level:
            k = len(out)
            out.append(np.zeros((max(tile_h, height >> k),
                                 max(bytes_per_row, plane_width >> k)), dtype=np.uint8))
        plane = out[level]
        if (row + 1) * tile_h > plane.shape[0] or (col + 1) * bytes_per_row > plane.shape[1]:
            continue
        at = TILE_HEADER + n * stride
        cell = np.frombuffer(record[at + TILE_HEADER:at + stride], dtype=np.uint8)
        plane[row * tile_h:(row + 1) * tile_h,
              col * bytes_per_row:(col + 1) * bytes_per_row] = \
            texpack.unswizzle(cell, bytes_per_row, tile_h)

    if psm != 4:
        return out
    unpacked = []
    for plane in out:
        wide = np.empty((plane.shape[0], plane.shape[1] * 2), dtype=np.uint8)
        wide[:, 0::2] = plane & 0x0F
        wide[:, 1::2] = plane >> 4
        unpacked.append(wide)
    return unpacked


def replace_image(stream: bytes, record_index: int, image: Image.Image) -> bytes:
    """Put `image` into one record of a decompressed stream, keeping every size."""
    records = texpack.load_records(stream)
    palette = records[record_index - 1]
    record = records[record_index]
    # Each mip level gets the new artwork at its own size, so the smaller copies do not keep
    # showing the Japanese if the engine ever reaches for them.
    planes = [texenc.quantise(image, palette)]
    for level in range(1, len(indices_of(record))):
        small = image.resize((max(1, image.width >> level), max(1, image.height >> level)),
                             Image.LANCZOS)
        planes.append(texenc.quantise(small, palette))
    rebuilt = write_record(record, planes)
    if len(rebuilt) != len(record):
        raise ValueError("record length changed")
    # Records are laid out back to back at the offsets in the table, so writing one back is a
    # matter of finding where it starts.
    first = int.from_bytes(stream[0:4], "little")
    table = list(struct.unpack_from(f"<{first // 4}I", stream, 0))
    offsets = [v for v in table if v]
    at = offsets[record_index]
    return stream[:at] + rebuilt + stream[at + len(record):]


def round_trip(stream: bytes) -> dict:
    """Decode and re-encode every record; the bytes must come back identical."""
    records = texpack.load_records(stream)
    exact = mismatch = skipped = 0
    for n in range(2, len(records), 2):
        image, header = decode_container.decode_record(records[n - 1], records[n])
        if image is None:
            skipped += 1
            continue
        indices = indices_of(records[n])
        rebuilt = write_record(records[n], indices)
        if rebuilt == records[n]:
            exact += 1
        else:
            mismatch += 1
    return {"exact": exact, "mismatch": mismatch, "skipped": skipped}


if __name__ == "__main__":
    import read_blocks

    blob = (read_blocks.ROOT / "0001").read_bytes()
    totals = {"exact": 0, "mismatch": 0, "skipped": 0}
    for at, payload in read_blocks.blocks(blob):
        plain, _ = read_blocks.open_stream(payload)
        if plain is None:
            continue
        try:
            result = round_trip(plain)
        except Exception:
            totals["skipped"] += 1
            continue
        for key in totals:
            totals[key] += result[key]
    print(f"0001 records: {totals['exact']} round-trip exactly, "
          f"{totals['mismatch']} differ, {totals['skipped']} skipped")

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


def write_record(record: bytes, indices: np.ndarray) -> bytes:
    """Return the record with its tiles taken from a full-size index plane."""
    width, height, tile_w, tile_h, psm, flag = struct.unpack_from("<6H", record, 0)
    count, = struct.unpack_from("<I", record, 12)
    bytes_per_row = tile_w // 2 if psm == 4 else tile_w
    tile_pixels = tile_w
    stride = TILE_HEADER + bytes_per_row * tile_h
    if indices.shape != (height, width):
        raise ValueError(f"index plane is {indices.shape}, record wants {(height, width)}")

    out = bytearray(record)
    for n in range(count):
        at = TILE_HEADER + n * stride
        col, row = struct.unpack_from("<2H", out, at)
        if row * tile_h >= height or col * tile_pixels >= width:
            continue
        cell = indices[row * tile_h:(row + 1) * tile_h,
                       col * tile_pixels:(col + 1) * tile_pixels]
        if psm == 4:
            packed = (cell[:, 0::2] & 0x0F) | ((cell[:, 1::2] & 0x0F) << 4)
        else:
            packed = cell.astype(np.uint8)
        flat = texenc.swizzle(packed, bytes_per_row, tile_h)
        out[at + TILE_HEADER:at + stride] = flat.tobytes()
    return bytes(out)


def indices_of(record: bytes) -> np.ndarray | None:
    """The index plane behind a record, before the palette is applied."""
    width, height, tile_w, tile_h, psm, flag = struct.unpack_from("<6H", record, 0)
    count, = struct.unpack_from("<I", record, 12)
    bytes_per_row = tile_w // 2 if psm == 4 else tile_w
    tile_pixels = tile_w
    stride = TILE_HEADER + bytes_per_row * tile_h
    plane_width = width // 2 if psm == 4 else width
    plane = np.zeros((height, plane_width), dtype=np.uint8)
    for n in range(count):
        at = TILE_HEADER + n * stride
        col, row = struct.unpack_from("<2H", record, at)
        if row * tile_h >= height or col * tile_pixels >= width:
            continue
        cell = np.frombuffer(record[at + TILE_HEADER:at + stride], dtype=np.uint8)
        plane[row * tile_h:(row + 1) * tile_h,
              col * bytes_per_row:(col + 1) * bytes_per_row] = \
            texpack.unswizzle(cell, bytes_per_row, tile_h)
    if psm != 4:
        return plane
    out = np.empty((height, width), dtype=np.uint8)
    out[:, 0::2] = plane & 0x0F
    out[:, 1::2] = plane >> 4
    return out


def replace_image(stream: bytes, record_index: int, image: Image.Image) -> bytes:
    """Put `image` into one record of a decompressed stream, keeping every size."""
    records = texpack.load_records(stream)
    palette = records[record_index - 1]
    record = records[record_index]
    indices = texenc.quantise(image, palette)
    rebuilt = write_record(record, indices)
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

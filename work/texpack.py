"""Decoder for the 원격수사 texture packs.

Container layout (per decompressed LZ11 stream):

    u32 table[]            absolute offsets of every record; table[0] == table size
    record 0               texture metadata
    record 1, 2            palette, image   for texture 0
    record 3, 4            palette, image   for texture 1
    ...

Metadata record 0:

    u32 section_offset[16] first entry points at the texture entry array
    entry[] (8 bytes)      u16 width, u16 height, u32 psm

`psm` is the PSP GE pixel format: 4 = GU_PSM_T4, 5 = GU_PSM_T8.
Image data is swizzled in 16x8 byte blocks.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

PSM_NAMES = {0: "5650", 1: "5551", 2: "4444", 3: "8888", 4: "T4", 5: "T8", 6: "T16", 7: "T32"}


@dataclass(frozen=True)
class Texture:
    index: int
    width: int
    height: int
    psm: int
    palette: bytes
    image: bytes

    @property
    def psm_name(self) -> str:
        return PSM_NAMES.get(self.psm, f"psm{self.psm}")

    @property
    def record_index(self) -> int:
        return self.index * 2 + 2


def load_records(data: bytes) -> list[bytes]:
    first = struct.unpack_from("<I", data, 0)[0]
    table = list(struct.unpack_from(f"<{first // 4}I", data, 0))
    offsets = [v for v in table if v]
    bounds = offsets + [len(data)]
    return [data[bounds[i] : bounds[i + 1]] for i in range(len(offsets))]


def load_textures(data: bytes) -> list[Texture]:
    records = load_records(data)
    meta = records[0]
    start = struct.unpack_from("<I", meta, 0)[0]
    end = struct.unpack_from("<I", meta, 4)[0]
    count = (end - start) // 8
    textures = []
    for i in range(count):
        width, height, psm = struct.unpack_from("<HHI", meta, start + i * 8)
        pal_i, img_i = i * 2 + 1, i * 2 + 2
        if img_i >= len(records):
            break
        textures.append(Texture(i, width, height, psm, records[pal_i], records[img_i]))
    return textures


def unswizzle(buf: np.ndarray, byte_width: int, height: int) -> np.ndarray:
    if byte_width % 16 or height % 8:
        return buf[: byte_width * height].reshape(height, byte_width)
    blocks_per_row = byte_width // 16
    block_rows = height // 8
    blocks = buf[: byte_width * height].reshape(block_rows, blocks_per_row, 8, 16)
    return blocks.transpose(0, 2, 1, 3).reshape(height, byte_width)


def decode(tex: Texture, swizzled: bool = True) -> Image.Image | None:
    if tex.psm == 4:
        byte_width = tex.width // 2
    elif tex.psm == 5:
        byte_width = tex.width
    else:
        return None
    needed = byte_width * tex.height
    if len(tex.image) < needed or needed == 0:
        return None
    buf = np.frombuffer(tex.image, dtype=np.uint8)
    plane = unswizzle(buf, byte_width, tex.height) if swizzled else buf[:needed].reshape(tex.height, byte_width)

    if tex.psm == 4:
        indices = np.empty((tex.height, tex.width), dtype=np.uint8)
        indices[:, 0::2] = plane & 0x0F
        indices[:, 1::2] = plane >> 4
    else:
        indices = plane

    colours = np.frombuffer(tex.palette, dtype=np.uint8)
    colours = colours[: (len(colours) // 4) * 4].reshape(-1, 4)
    if colours.shape[0] < int(indices.max()) + 1:
        pad = np.zeros((int(indices.max()) + 1 - colours.shape[0], 4), dtype=np.uint8)
        colours = np.vstack([colours, pad])
    return Image.fromarray(colours[indices], "RGBA")


def load_stream(path: Path) -> list[Texture]:
    return load_textures(path.read_bytes())

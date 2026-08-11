"""Nintendo-style LZ10/LZ11 decompressors (the 원격수사 archives use the 0x11 variant)."""

from __future__ import annotations


class LzssError(Exception):
    pass


def _header(data: bytes, offset: int) -> tuple[int, int, int]:
    """Return (kind, decompressed_size, payload_offset)."""
    kind = data[offset]
    if kind not in (0x10, 0x11):
        raise LzssError(f"unexpected LZSS type 0x{kind:02x} at 0x{offset:x}")
    size = int.from_bytes(data[offset + 1 : offset + 4], "little")
    pos = offset + 4
    if size == 0:
        size = int.from_bytes(data[offset + 4 : offset + 8], "little")
        pos = offset + 8
    return kind, size, pos


def decompress(data: bytes, offset: int = 0, limit: int | None = None) -> tuple[bytes, int]:
    """Decompress one LZ10/LZ11 stream. Returns (plain, bytes_consumed)."""
    kind, size, pos = _header(data, offset)
    if limit is not None and size > limit:
        raise LzssError(f"declared size {size} exceeds limit {limit}")
    end = len(data)
    out = bytearray()
    while len(out) < size:
        if pos >= end:
            raise LzssError("input exhausted")
        flags = data[pos]
        pos += 1
        for bit in range(7, -1, -1):
            if len(out) >= size:
                break
            if not (flags >> bit) & 1:
                if pos >= end:
                    raise LzssError("input exhausted (literal)")
                out.append(data[pos])
                pos += 1
                continue

            if kind == 0x10:
                if pos + 2 > end:
                    raise LzssError("input exhausted (lz10 match)")
                b1, b2 = data[pos], data[pos + 1]
                pos += 2
                length = (b1 >> 4) + 3
                disp = (((b1 & 0xF) << 8) | b2) + 1
            else:
                if pos + 1 > end:
                    raise LzssError("input exhausted (lz11 match)")
                b1 = data[pos]
                indicator = b1 >> 4
                if indicator == 0:
                    if pos + 3 > end:
                        raise LzssError("input exhausted (lz11 long)")
                    b2, b3 = data[pos + 1], data[pos + 2]
                    pos += 3
                    length = (((b1 & 0xF) << 4) | (b2 >> 4)) + 0x11
                    disp = (((b2 & 0xF) << 8) | b3) + 1
                elif indicator == 1:
                    if pos + 4 > end:
                        raise LzssError("input exhausted (lz11 xlong)")
                    b2, b3, b4 = data[pos + 1], data[pos + 2], data[pos + 3]
                    pos += 4
                    length = (((b1 & 0xF) << 12) | (b2 << 4) | (b3 >> 4)) + 0x111
                    disp = (((b3 & 0xF) << 8) | b4) + 1
                else:
                    if pos + 2 > end:
                        raise LzssError("input exhausted (lz11 short)")
                    b2 = data[pos + 1]
                    pos += 2
                    length = indicator + 1
                    disp = (((b1 & 0xF) << 8) | b2) + 1

            if disp > len(out):
                raise LzssError(f"back-reference {disp} beyond output {len(out)}")
            start = len(out) - disp
            for i in range(length):
                out.append(out[start + i])

    return bytes(out[:size]), pos - offset


def try_decompress(data: bytes, offset: int = 0, limit: int | None = None):
    try:
        return decompress(data, offset, limit)
    except (LzssError, IndexError):
        return None

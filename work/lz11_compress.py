"""LZ11 compressor matching the decoder the game uses.

Token layout (the exact inverse of `lzss.decompress`):

    flag byte, MSB first, one bit per token
      0 -> literal byte
      1 -> back-reference, whose first nibble selects the size class:
             0x2..0xF  2 bytes   length 3..16
             0x0       3 bytes   length 17..272
             0x1       4 bytes   length 273..65808
           displacement is always 12 bits, stored minus one, so 1..4096

Matches may overlap the current position — the decoder copies byte by byte — so a
run can be encoded as a 1-byte displacement with a long length, which is what makes
the long zero fills in these archives compress so hard.

Matching uses hash chains over 3-byte keys with lazy evaluation: a match is only
emitted if the next position cannot do better, which is worth a few percent over
plain greedy and costs little.
"""

from __future__ import annotations

import argparse
from pathlib import Path

MIN_MATCH = 3
MAX_MATCH = 0x111 + 0xFFFF     # 65808
MAX_DISP = 0x1000              # 4096


class Matcher:
    """Hash chains over 3-byte keys."""

    def __init__(self, data: bytes, max_chain: int) -> None:
        self.data = data
        self.max_chain = max_chain
        self.head: dict[int, int] = {}
        self.prev = [-1] * len(data)

    def key(self, pos: int) -> int:
        d = self.data
        return (d[pos] << 16) | (d[pos + 1] << 8) | d[pos + 2]

    def insert(self, pos: int) -> None:
        if pos + MIN_MATCH > len(self.data):
            return
        k = self.key(pos)
        self.prev[pos] = self.head.get(k, -1)
        self.head[k] = pos

    def find(self, pos: int, limit: int) -> tuple[int, int]:
        """Best (length, displacement) at pos, or (0, 0)."""
        data = self.data
        end = len(data)
        if pos + MIN_MATCH > end:
            return 0, 0
        best_len, best_disp = 0, 0
        floor = max(0, pos - MAX_DISP)
        candidate = self.head.get(self.key(pos), -1)
        chain = 0
        max_len = min(limit, end - pos)
        while candidate >= floor and chain < self.max_chain:
            chain += 1
            length = 0
            while length < max_len and data[candidate + length] == data[pos + length]:
                length += 1
            if length > best_len:
                best_len, best_disp = length, pos - candidate
                if best_len >= max_len:
                    break
            candidate = self.prev[candidate]
        if best_len < MIN_MATCH:
            return 0, 0
        return best_len, best_disp


def encode_match(length: int, disp: int) -> bytes:
    d = disp - 1
    if not (1 <= disp <= MAX_DISP):
        raise ValueError(f"displacement out of range: {disp}")
    if 3 <= length <= 16:
        return bytes([((length - 1) << 4) | (d >> 8), d & 0xFF])
    if 17 <= length <= 272:
        v = length - 0x11
        return bytes([v >> 4, ((v & 0xF) << 4) | (d >> 8), d & 0xFF])
    if 273 <= length <= MAX_MATCH:
        v = length - 0x111
        return bytes([0x10 | (v >> 12), (v >> 4) & 0xFF, ((v & 0xF) << 4) | (d >> 8), d & 0xFF])
    raise ValueError(f"length out of range: {length}")


def compress(data: bytes, max_chain: int = 64, lazy: bool = True) -> bytes:
    size = len(data)
    out = bytearray()
    if size < 0x1000000:
        out += bytes([0x11]) + size.to_bytes(3, "little")
    else:
        out += bytes([0x11, 0, 0, 0]) + size.to_bytes(4, "little")

    matcher = Matcher(data, max_chain)
    tokens: list[bytes | int] = []
    pos = 0
    while pos < size:
        length, disp = matcher.find(pos, MAX_MATCH)
        if length and lazy and pos + 1 < size:
            # only take the match if the next position cannot beat it
            matcher.insert(pos)
            nxt_len, nxt_disp = matcher.find(pos + 1, MAX_MATCH)
            if nxt_len > length:
                tokens.append(data[pos])
                pos += 1
                continue
            # the insert above already covered this position
            for i in range(pos + 1, min(pos + length, size)):
                matcher.insert(i)
            tokens.append(encode_match(length, disp))
            pos += length
            continue

        if length:
            for i in range(pos, min(pos + length, size)):
                matcher.insert(i)
            tokens.append(encode_match(length, disp))
            pos += length
        else:
            matcher.insert(pos)
            tokens.append(data[pos])
            pos += 1

    for start in range(0, len(tokens), 8):
        group = tokens[start : start + 8]
        flags = 0
        for i, token in enumerate(group):
            if isinstance(token, bytes):
                flags |= 1 << (7 - i)
        out.append(flags)
        for token in group:
            if isinstance(token, bytes):
                out += token
            else:
                out.append(token)
    return bytes(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--chain", type=int, default=64)
    parser.add_argument("--greedy", action="store_true")
    args = parser.parse_args()

    import lzss

    data = args.input.read_bytes()
    packed = compress(data, max_chain=args.chain, lazy=not args.greedy)
    plain, consumed = lzss.decompress(packed, 0)

    ok = plain == data and consumed == len(packed)
    print(f"{args.input.name}: {len(data)} -> {len(packed)} bytes "
          f"({len(packed) * 100 / max(1, len(data)):.1f}%)  round-trip {'OK' if ok else 'FAILED'}")
    if not ok:
        raise SystemExit("round-trip mismatch")
    if args.out:
        args.out.write_bytes(packed)
        print(f"-> {args.out}")


if __name__ == "__main__":
    main()

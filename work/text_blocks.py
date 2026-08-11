"""Locate text blocks by their markers instead of by guessing at content.

`07 1C` opens a text block and `12 10` closes it.  The opening marker occurs 8,852 times
in the stream and every single occurrence is outside text, so it identifies blocks with
no false positives — unlike scanning for text-looking bytes, which also picks up operand
data that happens to fall in the kana range and was almost certainly what derailed the
earlier length solver.

A block runs from the `07 1C` through the closing `12 10`; both edges are therefore
instruction boundaries we can trust completely.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import lzss
import opcodes

SRC = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR\0000")
STREAM1 = 0x27E000
TEXT_START = 0x2AC80

OPEN = bytes([0x07, 0x1C])
CLOSE = bytes([0x12, 0x10])
MAX_TEXT = 4096


@dataclass(frozen=True)
class Block:
    marker: int      # offset of 07 1C
    text: int        # first text byte
    text_end: int    # one past the last text byte (where 12 10 begins)
    end: int         # one past the closing 12 10

    @property
    def text_length(self) -> int:
        return self.text_end - self.text


def load_stream() -> bytes:
    return lzss.decompress(SRC.read_bytes(), STREAM1)[0]


def find_blocks(plain: bytes, validate: bool = True) -> list[Block]:
    """Blocks whose closing marker is found before the next opening one.

    Bounding the search by the next `07 1C` matters: without it a block whose own
    terminator is one of the rarer forms swallows its successors, which shows up as
    overlapping blocks and would corrupt every offset derived from them.

    Searching for the raw byte pair is not enough either.  `12 10` also occurs *inside*
    operands -- 0x1E is five bytes wide and four blocks carry `1e 00 13 12 10`, where the
    match is the tail of the instruction rather than the end of the text.  So each
    candidate is checked against the interpreter's own length rule and rejected unless
    the walk from the first text byte actually lands on it.
    """
    markers = []
    pos = TEXT_START
    while True:
        marker = plain.find(OPEN, pos)
        if marker < 0:
            break
        markers.append(marker)
        pos = marker + 2

    blocks = []
    for index, marker in enumerate(markers):
        limit = markers[index + 1] if index + 1 < len(markers) else len(plain)
        limit = min(limit, marker + 2 + MAX_TEXT)
        text = marker + 2
        close = plain.find(CLOSE, text, limit)
        while close >= 0 and validate and not opcodes.lands_on(plain, text, close):
            close = plain.find(CLOSE, close + 1, limit)
        if close < 0:
            continue
        blocks.append(Block(marker, text, close, close + 2))
    return blocks


def boundaries(blocks: list[Block]) -> set[int]:
    """Instruction boundaries we are certain of."""
    known = set()
    for block in blocks:
        known.add(block.marker)
        known.add(block.end)
    return known


def text_map(blocks: list[Block]) -> dict[int, int]:
    """marker offset -> total block size, so a walker can step over it in one go."""
    return {block.marker: block.end - block.marker for block in blocks}


if __name__ == "__main__":
    plain = load_stream()
    blocks = find_blocks(plain)
    lengths = [b.text_length for b in blocks]
    print(f"{len(blocks)} text blocks")
    print(f"   text length min {min(lengths)}, max {max(lengths)}, "
          f"total {sum(lengths)} bytes")
    gaps = []
    for a, b in zip(blocks, blocks[1:]):
        gaps.append(b.marker - a.end)
    print(f"   gap between blocks: min {min(gaps)}, median "
          f"{sorted(gaps)[len(gaps) // 2]}, max {max(gaps)}")
    print("\nfirst blocks:")
    for block in blocks[:5]:
        print(f"   marker 0x{block.marker:08x} text 0x{block.text:08x} "
              f"len {block.text_length:4d} end 0x{block.end:08x}")

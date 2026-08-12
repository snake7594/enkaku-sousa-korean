"""Disassemble a PSP executable without stopping at the first instruction capstone dislikes.

The Allegrex core has VFPU instructions capstone does not decode, and `Cs.disasm` gives up at
the first one -- from 0x8804000 it produced 1035 instructions out of roughly 298,000, which
looks like a working disassembly right up until you notice the file is 1.2 MB.

Stepping four bytes past each refusal and resuming covers the rest.  Undecoded words are kept
as placeholders so addresses stay right.
"""

from __future__ import annotations

import struct
from pathlib import Path

from capstone import CS_ARCH_MIPS, CS_MODE_32, CS_MODE_LITTLE_ENDIAN, Cs


class Word:
    """A word capstone would not decode, standing in so addresses do not shift."""

    def __init__(self, address: int, raw: int):
        self.address = address
        self.mnemonic = ".word"
        self.op_str = f"{raw:#010x}"
        self.size = 4


def segment(path: Path):
    blob = path.read_bytes()
    phoff, = struct.unpack_from("<I", blob, 28)
    p_offset, p_vaddr, _, p_filesz = struct.unpack_from("<4I", blob, phoff + 4)
    return blob, p_offset, p_vaddr, p_filesz


def disassemble(path: Path):
    blob, p_offset, p_vaddr, p_filesz = segment(path)
    code = blob[p_offset:p_offset + p_filesz]
    md = Cs(CS_ARCH_MIPS, CS_MODE_32 | CS_MODE_LITTLE_ENDIAN)
    out, at = [], 0
    while at < len(code) - 3:
        moved = False
        for insn in md.disasm(code[at:], p_vaddr + at):
            out.append(insn)
            at += insn.size
            moved = True
        if not moved:
            out.append(Word(p_vaddr + at, int.from_bytes(code[at:at + 4], "little")))
            at += 4
    return out, p_vaddr, p_vaddr - p_offset

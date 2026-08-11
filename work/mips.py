"""A small MIPS disassembler, enough to read the script interpreter.

Only the instructions the interpreter is likely to use are decoded — loads, arithmetic,
comparisons, branches and jumps.  Anything else is rendered as a raw word, which is fine
for reading control flow and spotting comparisons against opcode values.
"""

from __future__ import annotations

import struct

REG = ["zero", "at", "v0", "v1", "a0", "a1", "a2", "a3",
       "t0", "t1", "t2", "t3", "t4", "t5", "t6", "t7",
       "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7",
       "t8", "t9", "k0", "k1", "gp", "sp", "fp", "ra"]

SPECIAL = {
    0x00: "sll", 0x02: "srl", 0x03: "sra", 0x04: "sllv", 0x06: "srlv", 0x07: "srav",
    0x08: "jr", 0x09: "jalr", 0x0C: "syscall", 0x10: "mfhi", 0x12: "mflo",
    0x18: "mult", 0x19: "multu", 0x1A: "div", 0x1B: "divu",
    0x20: "add", 0x21: "addu", 0x22: "sub", 0x23: "subu",
    0x24: "and", 0x25: "or", 0x26: "xor", 0x27: "nor",
    0x2A: "slt", 0x2B: "sltu",
}

OPCODES = {
    0x02: "j", 0x03: "jal", 0x04: "beq", 0x05: "bne", 0x06: "blez", 0x07: "bgtz",
    0x08: "addi", 0x09: "addiu", 0x0A: "slti", 0x0B: "sltiu",
    0x0C: "andi", 0x0D: "ori", 0x0E: "xori", 0x0F: "lui",
    0x20: "lb", 0x21: "lh", 0x23: "lw", 0x24: "lbu", 0x25: "lhu",
    0x28: "sb", 0x29: "sh", 0x2B: "sw",
}

BRANCHES = {"beq", "bne", "blez", "bgtz"}
IMM_ARITH = {"addi", "addiu", "slti", "sltiu", "andi", "ori", "xori"}
MEMORY = {"lb", "lh", "lw", "lbu", "lhu", "sb", "sh", "sw"}


def signed(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


class Insn:
    __slots__ = ("addr", "word", "name", "rs", "rt", "rd", "sa", "imm", "target")

    def __init__(self, addr: int, word: int) -> None:
        self.addr = addr
        self.word = word
        op = word >> 26
        self.rs = (word >> 21) & 0x1F
        self.rt = (word >> 16) & 0x1F
        self.rd = (word >> 11) & 0x1F
        self.sa = (word >> 6) & 0x1F
        self.imm = word & 0xFFFF
        self.target = None
        if op == 0:
            self.name = SPECIAL.get(word & 0x3F, "?")
        elif op in (0x02, 0x03):
            self.name = OPCODES[op]
            self.target = ((addr + 4) & 0xF0000000) | ((word & 0x03FFFFFF) << 2)
        else:
            self.name = OPCODES.get(op, "?")
            if self.name in BRANCHES:
                self.target = addr + 4 + (signed(self.imm) << 2)

    def text(self) -> str:
        n = self.name
        if n == "?":
            return f".word 0x{self.word:08x}"
        if n in ("jr", "jalr"):
            return f"{n} ${REG[self.rs]}"
        if n in ("sll", "srl", "sra"):
            if self.word == 0:
                return "nop"
            return f"{n} ${REG[self.rd]}, ${REG[self.rt]}, {self.sa}"
        if n == "lui":
            return f"lui ${REG[self.rt]}, 0x{self.imm:04x}"
        if n in IMM_ARITH:
            return f"{n} ${REG[self.rt]}, ${REG[self.rs]}, {signed(self.imm)}"
        if n in MEMORY:
            return f"{n} ${REG[self.rt]}, {signed(self.imm)}(${REG[self.rs]})"
        if n in BRANCHES:
            if n in ("beq", "bne"):
                return f"{n} ${REG[self.rs]}, ${REG[self.rt]}, 0x{self.target:08x}"
            return f"{n} ${REG[self.rs]}, 0x{self.target:08x}"
        if n in ("j", "jal"):
            return f"{n} 0x{self.target:08x}"
        if n in ("mfhi", "mflo"):
            return f"{n} ${REG[self.rd]}"
        if n in ("mult", "multu", "div", "divu"):
            return f"{n} ${REG[self.rs]}, ${REG[self.rt]}"
        return f"{n} ${REG[self.rd]}, ${REG[self.rs]}, ${REG[self.rt]}"


def disassemble(data: bytes, file_off: int, vaddr: int, count: int) -> list[Insn]:
    words = struct.unpack_from(f"<{count}I", data, file_off)
    return [Insn(vaddr + i * 4, w) for i, w in enumerate(words)]

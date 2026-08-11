"""Locate the script interpreter by looking for dense opcode comparisons.

The interpreter has to test the byte it just fetched against opcode values, so its
dispatch code is unusually rich in immediate comparisons against small constants —
0x00 through roughly 0x20, the range the bytecode actually uses.  Ordinary game code
compares against small numbers too, but nowhere near as densely in one place.

Functions are delimited by their `jr $ra` returns, and each is scored by how many such
comparisons it contains near a byte load, since a dispatcher fetches before it tests.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import mips
from find_dispatch import FILE_BASE, TEXT_SIZE, TEXT_VADDR

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")

# opcode values we are confident the bytecode uses
KNOWN_OPCODES = {0x00, 0x01, 0x07, 0x09, 0x0E, 0x10, 0x11, 0x12, 0x13, 0x14, 0x1C}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args()

    data = BOOT.read_bytes()
    insns = mips.disassemble(data, FILE_BASE, TEXT_VADDR, TEXT_SIZE // 4)
    print(f"disassembled {len(insns)} instructions from 0x{TEXT_VADDR:08x}")

    # split into functions at `jr $ra`
    functions = []
    start = 0
    for i, insn in enumerate(insns):
        if insn.name == "jr" and insn.rs == 31:
            functions.append((start, i + 2))       # include the delay slot
            start = i + 2
    print(f"{len(functions)} function-shaped regions")

    scored = []
    for begin, end in functions:
        if end - begin < 8 or end - begin > 4000:
            continue
        body = insns[begin:end]
        loads = sum(1 for x in body if x.name == "lbu")
        if not loads:
            continue
        compares = 0
        hit_values = Counter()
        for x in body:
            if x.name in ("addiu", "sltiu", "slti", "andi", "ori", "xori"):
                value = mips.signed(x.imm)
                if -0x40 <= value <= 0x40:
                    compares += 1
                    if abs(value) in KNOWN_OPCODES:
                        hit_values[abs(value)] += 1
        score = compares + 4 * len(hit_values) + 2 * loads
        scored.append((score, begin, end, loads, compares, len(hit_values), hit_values))

    scored.sort(reverse=True)
    print(f"\ntop candidates (score, address, size, lbu, small-immediates, distinct opcode hits):")
    for score, begin, end, loads, compares, distinct, values in scored[: args.top]:
        addr = insns[begin].addr
        seen = " ".join(f"{v:02x}" for v in sorted(values))
        print(f"   0x{addr:08x}  {end - begin:5d} insns  score {score:4d}  "
              f"lbu {loads:3d}  imm {compares:3d}  opcodes[{seen}]")


if __name__ == "__main__":
    main()

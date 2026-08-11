"""Survey every function in the unnamed text/script module and rank interpreter candidates.

The module sits between objctrl.c and movie.c and is small enough to examine in full.
An interpreter has a recognisable shape: it walks a buffer, so it advances a pointer by
*varying* amounts rather than a fixed stride, and because the script stores file-relative
offsets it must add them to a base held in a global.  Functions are scored on those two
traits plus the density of comparisons against small opcode-sized constants.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import mips
from find_dispatch import FILE_BASE, TEXT_SIZE, TEXT_VADDR

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")
LO, HI = 0x08847800, 0x0884FDEC


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lo", type=lambda v: int(v, 0), default=LO)
    parser.add_argument("--hi", type=lambda v: int(v, 0), default=HI)
    parser.add_argument("--top", type=int, default=16)
    args = parser.parse_args()

    data = BOOT.read_bytes()
    insns = mips.disassemble(data, FILE_BASE, TEXT_VADDR, TEXT_SIZE // 4)

    functions = []
    start = 0
    for i, insn in enumerate(insns):
        if insn.name == "jr" and insn.rs == 31:
            functions.append((start, i + 2))
            start = i + 2

    rows = []
    for begin, end in functions:
        addr = insns[begin].addr
        if not (args.lo <= addr < args.hi):
            continue
        body = insns[begin:end]

        byte_loads = sum(1 for x in body if x.name == "lbu")
        word_loads = sum(1 for x in body if x.name == "lw")
        adds = sum(1 for x in body if x.name == "addu")
        calls = sum(1 for x in body if x.name == "jal")

        # pointer advanced by differing constants -> variable-length records
        steps = Counter()
        for x in body:
            if x.name == "addiu" and x.rt == x.rs:
                delta = mips.signed(x.imm)
                if 1 <= delta <= 16:
                    steps[delta] += 1
        distinct_steps = len(steps)

        small_cmp = sum(1 for x in body
                        if x.name in ("addiu", "sltiu", "slti")
                        and 0 <= mips.signed(x.imm) <= 0x40)

        # globals loaded via lui/addiu or lui/lw -> candidate buffer base
        globals_used = set()
        upper = {}
        for x in body:
            if x.name == "lui":
                upper[x.rt] = x.imm << 16
            elif x.name in ("lw", "addiu") and x.rs in upper:
                globals_used.add(upper[x.rs] + mips.signed(x.imm))

        score = (byte_loads * 3 + distinct_steps * 6 + small_cmp
                 + (10 if distinct_steps >= 4 else 0))
        rows.append((score, addr, end - begin, byte_loads, word_loads, adds,
                     calls, distinct_steps, sorted(steps), small_cmp, len(globals_used)))

    rows.sort(reverse=True)
    print(f"{len(rows)} functions in 0x{args.lo:08x}-0x{args.hi:08x}\n")
    print(f"{'addr':>12} {'insns':>6} {'lbu':>4} {'lw':>4} {'addu':>5} {'jal':>4} "
          f"{'steps':>5} {'cmp':>4} {'globals':>7}   step sizes")
    for row in rows[: args.top]:
        (score, addr, size, byte_loads, word_loads, adds, calls,
         distinct_steps, steps, small_cmp, n_globals) = row
        print(f"  0x{addr:08x} {size:6d} {byte_loads:4d} {word_loads:4d} {adds:5d} "
              f"{calls:4d} {distinct_steps:5d} {small_cmp:4d} {n_globals:7d}   {steps}")


if __name__ == "__main__":
    main()

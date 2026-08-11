"""Find the LZ11 decompressor, and from it the script buffer.

Chasing callers of the text routines diverged into general UI code, so this comes at the
problem from the data side instead.  The decompressor is easy to identify because the
format's own constants appear as immediates: matches are extended by 0x11 in the 3-byte
form and 0x111 in the 4-byte form, and displacements are stored minus one.  0x111 in
particular is rare enough in ordinary code to be a good fingerprint.

Whatever function holds those constants writes the decompressed stream, so the pointer
it returns or stores is the script buffer the interpreter walks.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

import mips
from find_dispatch import FILE_BASE, TEXT_SIZE, TEXT_VADDR

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")

SIGNATURE = {0x111, 0x11, 0xFFF, 0x1000}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args()

    data = BOOT.read_bytes()
    insns = mips.disassemble(data, FILE_BASE, TEXT_VADDR, TEXT_SIZE // 4)

    functions = []
    start = 0
    for i, insn in enumerate(insns):
        if insn.name == "jr" and insn.rs == 31:
            functions.append((start, i + 2))
            start = i + 2

    hits = []
    for begin, end in functions:
        if end - begin < 10 or end - begin > 2000:
            continue
        found = Counter()
        for insn in insns[begin:end]:
            if insn.name in ("addiu", "ori", "andi", "sltiu", "slti", "xori"):
                value = insn.imm
                signed = mips.signed(insn.imm)
                for candidate in (value, signed & 0xFFFF):
                    if candidate in SIGNATURE:
                        found[candidate] += 1
        if 0x111 in found:
            hits.append((len(found), begin, end, dict(found)))

    hits.sort(reverse=True)
    print(f"{len(hits)} functions contain the 0x111 constant\n")
    for distinct, begin, end, found in hits[: args.top]:
        addr = insns[begin].addr
        pretty = " ".join(f"0x{k:x}x{v}" for k, v in sorted(found.items()))
        print(f"   0x{addr:08x}  {end - begin:4d} insns  constants[{pretty}]")

    if not hits:
        print("no candidate; the decompressor may inline its constants differently")
        return

    # the best candidate's loads/stores tell us where the output buffer comes from
    _, begin, end, _ = hits[0]
    print(f"\nglobals referenced by the best candidate 0x{insns[begin].addr:08x}:")
    base = {}
    seen = []
    for insn in insns[begin:end]:
        if insn.name == "lui":
            base[insn.rt] = insn.imm << 16
        elif insn.name in ("lw", "sw") and insn.rs in base:
            seen.append((insn.name, base[insn.rs] + mips.signed(insn.imm), insn.addr))
    for name, addr, at in seen[:20]:
        print(f"   {name} 0x{addr:08x}   at 0x{at:08x}")


if __name__ == "__main__":
    main()

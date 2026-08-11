"""Collect every write to the script-pointer global at 0x089F62A4.

The context turned out to be a fixed global at 0x089F5E1C, so the script pointer is the
single word at 0x089F5E1C + 1160.  That makes the search exact rather than heuristic: the
earlier attempt matched on the displacement 1160 alone and swept in a different structure
that happens to use the same offset, which is how a 108-byte record array got mistaken for
the script buffer.

Two ways the address is formed, and both are counted:
    lui r, 0x089F ; addiu r, r, 24092 ; sw x, 1160(r)
    lui r, 0x089F ; sw x, 25252(r)
"""

from __future__ import annotations

import argparse
from pathlib import Path

import mips
from find_dispatch import FILE_BASE, TEXT_SIZE, TEXT_VADDR

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")
TARGET = 0x089F62A4
LOADS = ("lw", "lh", "lhu", "lb", "lbu")
STORES = ("sw", "sh", "sb")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=lambda v: int(v, 0), default=TARGET)
    parser.add_argument("--context", type=int, default=4)
    args = parser.parse_args()

    data = BOOT.read_bytes()
    insns = mips.disassemble(data, FILE_BASE, TEXT_VADDR, TEXT_SIZE // 4)

    base: dict[int, int] = {}
    reads, writes = [], []
    for i, insn in enumerate(insns):
        if insn.name == "lui":
            base[insn.rt] = insn.imm << 16
        elif insn.name == "addiu" and insn.rs in base:
            base[insn.rt] = base[insn.rs] + mips.signed(insn.imm)
        elif insn.rs in base and insn.name in LOADS + STORES:
            if base[insn.rs] + mips.signed(insn.imm) == args.target:
                (writes if insn.name in STORES else reads).append(i)
        # An array is reached by forming its address and then indexing, so the access never
        # carries the array's displacement -- searching only for load/store displacements
        # reports zero uses for a table the code plainly indexes.
        if insn.name == "addiu" and insn.rt in base and base[insn.rt] == args.target:
            reads.append(i)

    print(f"global 0x{args.target:08x}: {len(writes)} writes, {len(reads)} reads\n")
    for i in writes:
        print(f"write at 0x{insns[i].addr:08x}")
        for j in range(max(0, i - args.context), min(len(insns), i + 2)):
            body = insns[j].text() if callable(insns[j].text) else insns[j].text
            mark = "  <--" if j == i else ""
            print(f"   0x{insns[j].addr:08x}  {body}{mark}")
        print()

    print(f"read sites: {[f'0x{insns[i].addr:08x}' for i in reads[:20]]}")


if __name__ == "__main__":
    main()

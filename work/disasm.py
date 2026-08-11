"""Dump a disassembled range of the module, annotated for reading the interpreter."""

from __future__ import annotations

import argparse
from pathlib import Path

import mips
from find_dispatch import FILE_BASE, TEXT_SIZE, TEXT_VADDR, to_file

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--addr", type=lambda v: int(v, 0), required=True)
    parser.add_argument("--count", type=int, default=280)
    parser.add_argument("--marks", default="", help="comma-separated immediates to flag")
    args = parser.parse_args()

    data = BOOT.read_bytes()
    marks = {int(x, 0) for x in args.marks.split(",") if x.strip()}
    insns = mips.disassemble(data, to_file(args.addr), args.addr, args.count)

    targets = {i.target for i in insns if i.target}
    for insn in insns:
        label = ">" if insn.addr in targets else " "
        note = ""
        if insn.name in ("addiu", "sltiu", "slti", "andi", "ori", "xori"):
            value = mips.signed(insn.imm)
            if value in marks or abs(value) in marks:
                note = "   <== opcode constant"
        if insn.name == "lbu":
            note = "   <== byte fetch"
        print(f"{label} 0x{insn.addr:08x}  {insn.text():<44s}{note}")


if __name__ == "__main__":
    main()

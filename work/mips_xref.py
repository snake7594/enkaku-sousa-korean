"""Find every place in BOOT.BIN that forms an address in a given range.

MIPS builds a 32-bit address in two halves, and the second half can arrive as an `addiu`, an
`ori`, or folded into the offset of a load or store.  Matching only lui/addiu pairs misses the
last case, which is how the save menu's string table is reached -- so nothing turned up for it.

This disassembles the loaded segment, carries the value of each `lui` forward until the
register is written again, and reports any instruction whose effective address lands in the
range asked for.  Tracking is per straight-line run and resets at every branch target, which
is crude but does not need to be better: a lui and its partner are almost always adjacent.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from capstone import CS_ARCH_MIPS, CS_MODE_32, CS_MODE_LITTLE_ENDIAN, Cs

ROOT = Path(r"D:\psp\원격수사")
BOOT = ROOT / "iso_extract" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN"

LOADS = {"lw", "lh", "lhu", "lb", "lbu", "sw", "sh", "sb", "lwl", "lwr"}


def segment(path: Path):
    blob = path.read_bytes()
    phoff, = struct.unpack_from("<I", blob, 28)
    p_offset, p_vaddr, _, p_filesz = struct.unpack_from("<4I", blob, phoff + 4)
    return blob, p_offset, p_vaddr, p_filesz


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=BOOT)
    parser.add_argument("--target", type=lambda v: int(v, 0), required=True,
                        help="virtual address to look for")
    parser.add_argument("--window", type=int, default=4)
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()

    blob, p_offset, p_vaddr, p_filesz = segment(args.file)
    code = blob[p_offset:p_offset + p_filesz]
    md = Cs(CS_ARCH_MIPS, CS_MODE_32 | CS_MODE_LITTLE_ENDIAN)
    md.detail = True

    lo, hi = args.target, args.target + args.window
    upper = {}
    hits = []
    for insn in md.disasm(code, p_vaddr):
        name, ops = insn.mnemonic, insn.op_str
        if name == "lui":
            reg, _, imm = ops.partition(", ")
            try:
                upper[reg] = int(imm, 0) << 16
            except ValueError:
                upper.pop(reg, None)
            continue
        if name in ("addiu", "ori", "addi"):
            parts = [p.strip() for p in ops.split(",")]
            if len(parts) == 3 and parts[1] in upper:
                try:
                    value = int(parts[2], 0)
                except ValueError:
                    value = None
                if value is not None:
                    if name != "ori" and value & 0x8000:
                        value -= 0x10000
                    addr = (upper[parts[1]] + value) & 0xFFFFFFFF
                    if lo <= addr < hi:
                        hits.append((insn.address, f"{name} {ops}", addr))
                    upper[parts[0]] = addr
                    continue
            upper.pop(parts[0] if parts else "", None)
            continue
        if name in LOADS and "(" in ops:
            offset, _, base = ops.rpartition("(")
            base = base.rstrip(")")
            offset = offset.split(",")[-1].strip()
            if base in upper:
                try:
                    value = int(offset, 0)
                except ValueError:
                    value = None
                if value is not None:
                    if value & 0x8000:
                        value -= 0x10000
                    addr = (upper[base] + value) & 0xFFFFFFFF
                    if lo <= addr < hi:
                        hits.append((insn.address, f"{name} {ops}", addr))
            continue
        # anything else that writes a register invalidates what we knew about it
        first = ops.split(",")[0].strip()
        if first.startswith("$"):
            upper.pop(first, None)

    print(f"{len(hits)} instructions form an address in {lo:#x}..{hi:#x}")
    for addr, text, formed in hits[: args.limit]:
        print(f"   {addr:#010x}  {text:38s} -> {formed:#x}")


if __name__ == "__main__":
    main()

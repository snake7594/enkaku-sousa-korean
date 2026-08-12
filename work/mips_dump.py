"""Print a stretch of BOOT.BIN's disassembly, with the values lui builds resolved.

Reading MIPS by eye is much easier when the two halves of an address are already joined, so
this carries each lui forward and annotates the instruction that completes it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mipsdis import disassemble

ROOT = Path(r"D:\psp\원격수사")
BOOT = ROOT / "iso_extract" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN"
LOADS = {"lw", "lh", "lhu", "lb", "lbu", "sw", "sh", "sb"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=BOOT)
    parser.add_argument("--start", type=lambda v: int(v, 0), required=True)
    parser.add_argument("--end", type=lambda v: int(v, 0), required=True)
    args = parser.parse_args()

    listing, base, delta = disassemble(args.file)
    upper = {}
    for insn in listing:
        if not (args.start <= insn.address < args.end):
            if insn.address >= args.end:
                break
            continue
        note = ""
        name, ops = insn.mnemonic, insn.op_str
        parts = [p.strip() for p in ops.split(",")]
        if name == "lui":
            try:
                upper[parts[0]] = int(parts[1], 0) << 16
            except (ValueError, IndexError):
                pass
        elif name in ("addiu", "ori") and len(parts) == 3 and parts[1] in upper:
            try:
                # capstone already prints the signed immediate, so sign-extending again
                # shifts the address by 0x10000 -- that is how 0x88ea760 was read as
                # 0x88da760 and sent me to look at compressed data
                value = int(parts[2], 0)
                upper[parts[0]] = (upper[parts[1]] + value) & 0xFFFFFFFF
                note = f"   ; = {upper[parts[0]]:#x}"
            except ValueError:
                pass
        elif name in LOADS and "(" in ops:
            head, _, tail = ops.rpartition("(")
            reg = tail.rstrip(")")
            if reg in upper:
                try:
                    value = int(head.split(",")[-1].strip(), 0)
                    if value & 0x8000:
                        value -= 0x10000
                    note = f"   ; [{(upper[reg] + value) & 0xFFFFFFFF:#x}]"
                except ValueError:
                    pass
        elif parts and parts[0].startswith("$"):
            upper.pop(parts[0], None)
        print(f"{insn.address:#010x}  {insn.mnemonic:9s} {insn.op_str}{note}")


if __name__ == "__main__":
    main()

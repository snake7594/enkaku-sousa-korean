"""Recover operand sizes by summing the advances along a handler's path, not listing them.

The previous pass reported opcode 0x1C as `[1, 2, 4]` and read that as three alternative
lengths.  It is not a choice -- 0x0884F260 is straight-line code that bumps the same
register five times and stores it back after each one:

    lw $v1, 1160($a1) / +1 sw / +2 sw / +4 sw / +4 sw / +4 sw / jr $ra

so the operand is 1+2+4+4+4 = 15 bytes and the instruction is 16.  Every multi-advance
handler was mis-read the same way, which is why 0x1C looked like a two-byte instruction and
the parser walked straight into the text after it.

So this follows the fall-through path and accumulates, treating a store as a checkpoint
rather than an outcome.  Where a handler really does branch before its stores, both the
fall-through total and the presence of the branch are reported instead of being flattened
into a single number that would be wrong on one of the paths.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mips
from find_dispatch import to_file

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")
TABLE = Path(r"D:\psp\원격수사\build\opcode_table.json")
PC_FIELD = 1160
MAX_OPCODE = 0x1C
BRANCHES = ("beq", "bne", "bgez", "blez", "bgtz", "bltz", "beql", "bnel")


def walk(data: bytes, addr: int, field: int, limit: int = 300) -> tuple[int, bool, int]:
    """Sum the advances on the fall-through path.  Returns (total, branched, stores)."""
    insns = mips.disassemble(data, to_file(addr), addr, limit)
    total, branched, stores = 0, False, 0
    # only registers that actually hold the script pointer count.  Tracking every addiu
    # swept in `addiu $sp, $sp, -16` and produced negative "lengths".
    holds: dict[int, int] = {}
    ending = False
    for insn in insns:
        if insn.name == "lw" and mips.signed(insn.imm) == field:
            holds[insn.rt] = 0
        elif insn.name == "addiu" and insn.rs in holds:
            holds[insn.rt] = holds[insn.rs] + mips.signed(insn.imm)
        elif insn.name == "sw" and mips.signed(insn.imm) == field and insn.rt in holds:
            total = holds[insn.rt]
            stores += 1
        elif insn.name in BRANCHES:
            branched = True
        elif insn.name == "jr" and insn.rs == 31:
            ending = True          # the delay slot still runs, and often holds the last store
            continue
        if ending:
            break
    return total, branched, stores


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        default=Path(r"D:\psp\원격수사\build\lengths_v3.json"))
    args = parser.parse_args()

    data = BOOT.read_bytes()
    handlers = {int(k, 16): v for k, v in json.loads(TABLE.read_text())["handlers"].items()
                if int(k, 16) <= MAX_OPCODE}
    counts = {int(k, 16): v for k, v in
              json.loads(Path(r"D:\psp\원격수사\build\arg_counts.json").read_text())["args"].items()}

    table = {}
    print(f"{'op':>4} {'handler':>10} {'inline':>7} {'args':>5} {'total':>6}  note")
    for code in sorted(handlers):
        inline, branched, stores = walk(data, handlers[code], PC_FIELD)
        nargs = counts.get(code, 0)
        table[code] = {"inline": inline, "args": nargs, "base": 1 + inline}
        note = f"{stores} stores" + ("; branches before a store" if branched else "")
        print(f"  {code:02x} 0x{handlers[code]:08x} {inline:7d} {nargs:5d} "
              f"{1 + inline:6d}  {note}")

    print("\ntotal = 1 (opcode) + inline + per argument (1 tag + payload)")
    args.out.write_text(json.dumps(
        {"lengths": {f"{k:02x}": v for k, v in sorted(table.items())}}, indent=1),
        encoding="utf-8")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

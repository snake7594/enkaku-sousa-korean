"""Extract the instruction-length table straight out of the interpreter.

The interpreter at 0x0884A030 keeps its script pointer in the context struct at offset
17016.  Every opcode handler finishes by loading that pointer, adding its own instruction
size and storing it back, so the sizes are written down in the code — no inference
needed, which is exactly what four rounds of statistical guessing could not provide.

Handlers are reached by a chain of `addiu $v0, $zero, <code>` followed by a branch on
$s0, so the branch targets label each handler with the opcode it serves.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import mips
from find_dispatch import to_file

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")
INTERP = 0x0884A030
COUNT = 620
PC_FIELD = 17016          # ctx + 0x4278 holds the script pointer


def decode_branch(word: int) -> tuple[str, int, int, int] | None:
    """BEQL/BNEL are not in the small disassembler; decode them here."""
    op = word >> 26
    if op not in (0x14, 0x15):
        return None
    rs = (word >> 21) & 0x1F
    rt = (word >> 16) & 0x1F
    imm = word & 0xFFFF
    return ("beql" if op == 0x14 else "bnel", rs, rt, mips.signed(imm))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--addr", type=lambda v: int(v, 0), default=INTERP)
    parser.add_argument("--count", type=int, default=COUNT)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    data = BOOT.read_bytes()
    insns = mips.disassemble(data, to_file(args.addr), args.addr, args.count)
    by_addr = {x.addr: i for i, x in enumerate(insns)}

    # map handler entry -> opcode, from the comparison chain on $s0
    handler_of: dict[int, int] = {}
    pending = None
    for i, insn in enumerate(insns):
        if insn.name == "addiu" and insn.rs == 0 and insn.rt == 2:      # addiu $v0, $zero, K
            pending = mips.signed(insn.imm)
            continue
        target = None
        if insn.name == "beq" and insn.rs == 16 and insn.rt == 2:        # beq $s0, $v0
            target = insn.target
        else:
            decoded = decode_branch(insn.word)
            if decoded and decoded[0] == "beql" and decoded[1] == 16 and decoded[2] == 2:
                target = insn.addr + 4 + (decoded[3] << 2)
        if target is not None and pending is not None:
            handler_of.setdefault(target, pending)
    print(f"{len(handler_of)} handler entries labelled with an opcode")

    # every point where the script pointer is advanced
    advances = []
    for i, insn in enumerate(insns):
        if insn.name != "sw" or mips.signed(insn.imm) != PC_FIELD:
            continue
        reg = insn.rt
        for j in range(max(0, i - 6), i):
            prev = insns[j]
            if prev.name == "addiu" and prev.rt == reg and prev.rs == reg:
                advances.append((insn.addr, mips.signed(prev.imm)))
                break
    print(f"{len(advances)} script-pointer advances found")

    # attribute each advance to the handler it sits in
    entries = sorted(handler_of)
    table: dict[int, set] = defaultdict(set)
    for addr, delta in advances:
        owner = None
        for entry in entries:
            if entry <= addr:
                owner = entry
            else:
                break
        if owner is not None:
            table[handler_of[owner]].add(delta)

    print("\nopcode -> instruction length (bytes):")
    for code in sorted(table):
        sizes = sorted(table[code])
        note = "" if len(sizes) == 1 else "   (multiple; handler has branches)"
        print(f"   0x{code:02x} : {sizes}{note}")

    if args.out:
        args.out.write_text(json.dumps(
            {f"{k:02x}": sorted(v) for k, v in sorted(table.items())}, indent=1),
            encoding="utf-8")
        print(f"-> {args.out}")


if __name__ == "__main__":
    main()

"""Read the opcode dispatch table at 0x089241D8 and recover the real instruction lengths.

The crash handed over the thing four rounds of statistics were substituting for.  The code
at 0x0884F86C reads a byte, shifts it left two, adds it to 0x089241D8, loads a word and
calls it -- so there is a jump table indexed by opcode after all, and the note in ANALYSIS
saying none exists was wrong.

It also shows the interpreter I reverse-engineered was the wrong one.  That one keeps its
script pointer at ctx+17016; this one uses ctx+1160 and is what actually runs the scene
script.  The length model built from the other function happened to walk the stream without
desyncing, which is why it passed every check -- but agreeing with the bytes is not the same
as being the code that reads them.

Each handler advances ctx+1160 by its operand size, so the table gives the opcode set and
the handlers give the lengths, both by observation rather than inference.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import mips
from find_dispatch import to_file

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")
TABLE = 0x089241D8
PC_FIELD = 1160
CODE_LO, CODE_HI = 0x08804000, 0x08920000


def advance(data: bytes, handler: int, limit: int = 90, field: int = PC_FIELD) -> list[int]:
    """How much the handler adds to the script pointer -- operand bytes, opcode excluded.

    Two idioms, and only recognising the first is what made 21 handlers look like they take
    no operands.  Top-level handlers reach the field through the context struct and rewrite
    it in place (`addiu $x, $x, N`); the argument readers are handed the field's *address*
    and copy into a different register (`addiu $dst, $src, N`), so requiring rs == rt misses
    every one of them.
    """
    insns = mips.disassemble(data, to_file(handler), handler, limit)
    deltas = []
    for i, insn in enumerate(insns):
        if insn.name == "sw" and mips.signed(insn.imm) == field:
            for j in range(max(0, i - 10), i):
                prev = insns[j]
                if prev.name == "addiu" and prev.rt == insn.rt:
                    deltas.append(mips.signed(prev.imm))
                    break
        if insn.name == "jr" and insn.rs == 31:
            break
    return deltas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", type=lambda v: int(v, 0), default=TABLE)
    parser.add_argument("--entries", type=int, default=256)
    parser.add_argument("--field", type=int, default=PC_FIELD,
                        help="displacement the routine writes the pointer back through; "
                             "1160 for top-level handlers, 0 for argument readers")
    parser.add_argument("--out", type=Path,
                        default=Path(r"D:\psp\원격수사\build\opcode_table.json"))
    args = parser.parse_args()

    data = BOOT.read_bytes()
    base = to_file(args.table)
    words = struct.unpack_from(f"<{args.entries}I", data, base)

    valid = {i: w for i, w in enumerate(words) if CODE_LO <= w < CODE_HI}
    print(f"table at 0x{args.table:08x}: {len(valid)}/{args.entries} entries are code addresses")
    distinct = sorted(set(valid.values()))
    print(f"   {len(distinct)} distinct handlers")
    bad = [i for i, w in enumerate(words) if not (CODE_LO <= w < CODE_HI)]
    print(f"   {len(bad)} slots are not code (first few values: "
          f"{[hex(words[i]) for i in bad[:5]]})")

    lengths = {}
    print(f"\n{'op':>4} {'handler':>10}  advance")
    for code in sorted(valid):
        deltas = advance(data, valid[code], field=args.field)
        unique = sorted(set(deltas))
        lengths[code] = unique
        note = "" if len(unique) <= 1 else "  (branches)"
        print(f"  {code:02x} 0x{valid[code]:08x}  "
              f"{unique if unique else 'none -- opcode byte only'}{note}")

    args.out.write_text(json.dumps({
        "table": args.table,
        "handlers": {f"{k:02x}": v for k, v in sorted(valid.items())},
        "operand_bytes": {f"{k:02x}": v for k, v in sorted(lengths.items())},
    }, indent=1), encoding="utf-8")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

"""Count how many arguments each opcode reads, completing the instruction model.

Length is not a per-opcode constant: an instruction is the opcode byte plus N arguments,
each of which announces its own size with a type tag.  So the only thing still missing is N.

Handlers read an argument by calling a routine with the *address* of the script-pointer
field, which shows up as `addiu $a0, $a1, 1160` in the call's delay slot.  Counting those
calls per handler gives N -- but only when the calls are straight-line.  A handler that
reads arguments in a loop, or on both sides of a branch, has no single N, and those are
reported rather than averaged into a number that would be wrong everywhere.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import mips
from find_dispatch import to_file

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")
TABLE = Path(r"D:\psp\원격수사\build\opcode_table.json")
PC_FIELD = 1160
MAX_OPCODE = 0x1C


def body(data: bytes, addr: int, limit: int = 400):
    out = []
    for insn in mips.disassemble(data, to_file(addr), addr, limit):
        out.append(insn)
        if insn.name == "jr" and insn.rs == 31 and len(out) > 4:
            out.append(mips.disassemble(data, to_file(insn.addr + 4), insn.addr + 4, 1)[0])
            break
    return out


def arg_calls(insns) -> tuple[list[int], bool]:
    """Call sites that hand over the script-pointer field, and whether control flow forks."""
    calls, forked = [], False
    for i, insn in enumerate(insns):
        if insn.name == "jal" and i + 1 < len(insns):
            delay = insns[i + 1]
            if delay.name == "addiu" and mips.signed(delay.imm) == PC_FIELD:
                calls.append(insn.target)
        # a backward branch means a loop, so the count is data-dependent
        if insn.name in ("beq", "bne", "bgez", "blez", "bgtz", "bltz") and insn.target:
            if insn.target <= insn.addr:
                forked = True
    return calls, forked


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        default=Path(r"D:\psp\원격수사\build\arg_counts.json"))
    args = parser.parse_args()

    data = BOOT.read_bytes()
    handlers = {int(k, 16): v for k, v in json.loads(TABLE.read_text())["handlers"].items()
                if int(k, 16) <= MAX_OPCODE}

    counts, readers, tricky = {}, Counter(), []
    print(f"{'op':>4} {'handler':>10} {'args':>5}  readers / note")
    for code in sorted(handlers):
        insns = body(data, handlers[code])
        calls, forked = arg_calls(insns)
        counts[code] = len(calls)
        readers.update(calls)
        note = ", ".join(f"0x{c:08x}" for c in dict.fromkeys(calls)) or "-"
        if forked and calls:
            tricky.append(code)
            note += "   <- has a backward branch; count may be data-dependent"
        print(f"  {code:02x} 0x{handlers[code]:08x} {len(calls):5d}  {note}")

    print(f"\nargument readers used: "
          f"{[(f'0x{t:08x}', n) for t, n in readers.most_common()]}")
    print(f"{sum(counts.values())} argument reads across {len(counts)} opcodes; "
          f"{sum(1 for v in counts.values() if not v)} opcodes take none")
    if tricky:
        print(f"loop/branch handlers to treat with care: {[f'0x{c:02x}' for c in tricky]}")

    args.out.write_text(json.dumps(
        {"args": {f"{k:02x}": v for k, v in sorted(counts.items())},
         "uncertain": [f"{c:02x}" for c in tricky]}, indent=1), encoding="utf-8")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

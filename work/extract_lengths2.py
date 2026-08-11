"""Extract the full instruction-length table from the interpreter's dispatch chains.

The first pass caught only 14 handlers because it recorded one opcode per handler entry,
while several codes share a handler (0x00, 0x13, 0x14 and 0x15 all branch to the same
place), and because it attributed pointer advances by nearest-preceding-entry, which
leaks across handler boundaries.

This version keeps every opcode that reaches an entry, bounds each handler at the next
entry so an advance is only credited to the block it really sits in, and scans the other
candidate functions in the module as well — a code absent from one dispatcher is likely
handled by another.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import mips
from find_dispatch import to_file

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")
PC_FIELD = 17016
FUNCTIONS = [(0x0884A030, 620), (0x0884B680, 520), (0x0884E3DC, 410)]


def decode_branch(word: int):
    op = word >> 26
    if op not in (0x14, 0x15):
        return None
    return (op, (word >> 21) & 0x1F, (word >> 16) & 0x1F, mips.signed(word & 0xFFFF))


def scan(data: bytes, addr: int, count: int, table: dict[int, set], notes: list[str]) -> None:
    insns = mips.disassemble(data, to_file(addr), addr, count)
    lo, hi = addr, addr + count * 4

    # opcode -> handler entry, allowing several opcodes to share one entry
    entry_codes: dict[int, set[int]] = defaultdict(set)
    pending = None
    for insn in insns:
        if insn.name == "addiu" and insn.rs == 0 and insn.rt == 2:
            pending = mips.signed(insn.imm)
            continue
        target = None
        if insn.name == "beq" and insn.rs == 16 and insn.rt == 2:
            target = insn.target
        else:
            decoded = decode_branch(insn.word)
            if decoded and decoded[0] == 0x14 and decoded[1] == 16 and decoded[2] == 2:
                target = insn.addr + 4 + (decoded[3] << 2)
        if target is not None and pending is not None and lo <= target < hi:
            entry_codes[target].add(pending)

    entries = sorted(entry_codes)
    if not entries:
        return

    # advances, credited only to the handler block they fall inside
    for i, insn in enumerate(insns):
        if insn.name != "sw" or mips.signed(insn.imm) != PC_FIELD:
            continue
        reg = insn.rt
        delta = None
        for j in range(max(0, i - 6), i):
            prev = insns[j]
            if prev.name == "addiu" and prev.rt == reg and prev.rs == reg:
                delta = mips.signed(prev.imm)
        if delta is None or delta <= 0:
            continue
        owner = None
        for k, entry in enumerate(entries):
            end = entries[k + 1] if k + 1 < len(entries) else hi
            if entry <= insn.addr < end:
                owner = entry
                break
        if owner is None:
            notes.append(f"advance {delta} at 0x{insn.addr:08x} outside any handler")
            continue
        for code in entry_codes[owner]:
            table[code].add(delta)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    data = BOOT.read_bytes()
    table: dict[int, set] = defaultdict(set)
    notes: list[str] = []
    for addr, count in FUNCTIONS:
        before = sum(len(v) for v in table.values())
        scan(data, addr, count, table, notes)
        after = sum(len(v) for v in table.values())
        print(f"0x{addr:08x}: contributed {after - before} length facts")

    print(f"\n{len(table)} opcodes with a length:")
    settled = {}
    for code in sorted(table):
        sizes = sorted(table[code])
        if len(sizes) == 1:
            settled[code] = sizes[0]
            print(f"   0x{code:02x} : {sizes[0]}")
        else:
            print(f"   0x{code:02x} : {sizes}   (handler branches; needs a closer read)")

    known = {0x00, 0x01, 0x02, 0x03, 0x07, 0x09, 0x0C, 0x0E, 0x0F, 0x10, 0x11,
             0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1E, 0x1F}
    missing = sorted(known - set(table))
    print(f"\nstill missing: {[f'0x{c:02x}' for c in missing]}")
    if notes:
        print(f"\n{len(notes)} advances could not be attributed (first few):")
        for note in notes[:6]:
            print("   " + note)

    if args.out:
        args.out.write_text(json.dumps({
            "settled": {f"{k:02x}": v for k, v in sorted(settled.items())},
            "ambiguous": {f"{k:02x}": sorted(v) for k, v in sorted(table.items())
                          if len(v) > 1},
        }, indent=1), encoding="utf-8")
        print(f"-> {args.out}")


if __name__ == "__main__":
    main()

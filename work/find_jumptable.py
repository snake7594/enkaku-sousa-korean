"""Locate jump tables in the module by recognising the MIPS dispatch idiom.

A byte-code interpreter dispatches with: load the opcode, scale it by four, add a table
base built from lui/addiu, load the handler address, and jump to it.  Searching for that
instruction shape finds the table far more reliably than guessing at data that merely
looks like pointers — the earlier candidate turned out to sit next to unrelated strings.

Only the handful of instructions the idiom needs are decoded.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from find_dispatch import TEXT_SIZE, TEXT_VADDR, to_file, to_vaddr

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")
FILE_BASE = 0x54


def decode(word: int) -> tuple[str, int, int, int, int]:
    op = word >> 26
    rs = (word >> 21) & 0x1F
    rt = (word >> 16) & 0x1F
    rd = (word >> 11) & 0x1F
    sa = (word >> 6) & 0x1F
    funct = word & 0x3F
    imm = word & 0xFFFF
    if op == 0 and funct == 0x08:
        return ("jr", rs, 0, 0, 0)
    if op == 0 and funct == 0x00:
        return ("sll", rd, rt, sa, 0)
    if op == 0 and funct == 0x21:
        return ("addu", rd, rs, rt, 0)
    if op == 0x0F:
        return ("lui", rt, 0, 0, imm)
    if op == 0x09:
        return ("addiu", rt, rs, 0, imm)
    if op == 0x23:
        return ("lw", rt, rs, 0, imm)
    if op == 0x24:
        return ("lbu", rt, rs, 0, imm)
    if op == 0x0B:
        return ("sltiu", rt, rs, 0, imm)
    return ("?", 0, 0, 0, 0)


def signed(imm: int) -> int:
    return imm - 0x10000 if imm & 0x8000 else imm


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", type=int, default=16, help="instructions to look back")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    data = BOOT.read_bytes()
    words = struct.unpack_from(f"<{TEXT_SIZE // 4}I", data, FILE_BASE)

    found = []
    for i, word in enumerate(words):
        name, rs, *_ = decode(word)
        if name != "jr" or rs == 31:      # skip returns
            continue
        # walk back for the table base and the scaling
        regs: dict[int, int] = {}
        saw_sll = False
        table = None
        for j in range(max(0, i - args.window), i):
            n, a, b, c, imm = decode(words[j])
            if n == "lui":
                regs[a] = imm << 16
            elif n == "addiu" and b in regs:
                regs[a] = regs[b] + signed(imm)
            elif n == "addiu" and b == 0:
                regs[a] = signed(imm)
            elif n == "sll" and c == 2:
                saw_sll = True
            elif n == "lw":
                base = regs.get(b)
                if base is not None:
                    table = base + signed(imm)
        if saw_sll and table and TEXT_VADDR <= table < TEXT_VADDR + 0x300000:
            found.append((to_vaddr(FILE_BASE + i * 4), table))

    print(f"{len(found)} dispatch-shaped sites\n")
    seen: dict[int, int] = {}
    for site, table in found:
        seen[table] = seen.get(table, 0) + 1
    for table, count in sorted(seen.items(), key=lambda kv: -kv[1])[: args.top]:
        offset = to_file(table)
        entries = 0
        if 0 <= offset < len(data) - 4:
            while offset + entries * 4 + 4 <= len(data):
                value = struct.unpack_from("<I", data, offset + entries * 4)[0]
                if not (TEXT_VADDR <= value < TEXT_VADDR + TEXT_SIZE and value % 4 == 0):
                    break
                entries += 1
        print(f"   table 0x{table:08x} (file 0x{offset:06x})  used by {count} site(s), "
              f"{entries} consecutive handler entries")


if __name__ == "__main__":
    main()

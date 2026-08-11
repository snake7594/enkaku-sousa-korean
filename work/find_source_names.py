"""Extract the source filenames the executable still carries, and locate their users.

The allocator is called as `alloc(size, align, __FILE__, __LINE__)`, so the module names
survive in the binary.  That turns anonymous addresses into named code: instead of
guessing which function interprets the script, we can look for a module whose name says
so and work from the code that references its string.
"""

from __future__ import annotations

import argparse
import re
import struct
from collections import defaultdict
from pathlib import Path

import mips
from find_dispatch import FILE_BASE, TEXT_SIZE, TEXT_VADDR

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")

PATTERN = re.compile(rb"[A-Za-z0-9_./\\-]{2,60}\.(?:c|cpp|cc|h)\x00")
INTERESTING = ("scr", "msg", "text", "str", "cmd", "seq", "event", "talk", "adv",
               "vm", "inter", "exec", "flow", "sys", "game", "font", "win", "disp")


def to_vaddr(offset: int) -> int:
    return offset - FILE_BASE + TEXT_VADDR


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="list every name, not just likely ones")
    args = parser.parse_args()

    data = BOOT.read_bytes()
    names = []
    for match in PATTERN.finditer(data):
        text = match.group()[:-1].decode("ascii")
        names.append((match.start(), to_vaddr(match.start()), text))
    print(f"{len(names)} source filenames found\n")

    # which code references each string, via lui/addiu pairs
    insns = mips.disassemble(data, FILE_BASE, TEXT_SIZE // 4 * 0 + TEXT_VADDR, TEXT_SIZE // 4)
    refs: dict[int, list[int]] = defaultdict(list)
    upper: dict[int, int] = {}
    for insn in insns:
        if insn.name == "lui":
            upper[insn.rt] = insn.imm << 16
        elif insn.name == "addiu" and insn.rs in upper:
            target = upper[insn.rs] + mips.signed(insn.imm)
            refs[target].append(insn.addr)

    by_vaddr = {vaddr: text for _, vaddr, text in names}
    shown = 0
    for _, vaddr, text in names:
        low = text.lower()
        if not args.all and not any(k in low for k in INTERESTING):
            continue
        sites = refs.get(vaddr, [])
        where = ", ".join(f"0x{a:08x}" for a in sites[:4])
        print(f"   {text:<28s} @0x{vaddr:08x}  {len(sites):3d} ref(s)  {where}")
        shown += 1
    print(f"\n{shown} names shown"
          + ("" if args.all else " (use --all for the complete list)"))


if __name__ == "__main__":
    main()

"""Disassemble around a return address, to see what the game was calling when it died.

PPSSPP reports `Destination: CPU Jump to 000001b4, RA: 0884f898`, so the call site is at
0x0884F890 and it went through a register rather than to a fixed label -- the game loaded a
value, treated it as code, and 0x1B4 is not code.

Which value matters: a remapped stream offset would land in the 0x02AC80-0x170A23 range, not
at 0x1B4, so this is not a pointer that was rewritten wrongly.  Something smaller is being
read -- an index, a count, a field that was never a pointer -- which points at a rewrite
that landed on data the patch had no business touching.  The instructions before the call
say which.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import mips
from find_dispatch import to_file

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--addr", type=lambda v: int(v, 0), default=0x0884F840)
    parser.add_argument("--count", type=int, default=40)
    args = parser.parse_args()

    data = BOOT.read_bytes()
    for insn in mips.disassemble(data, to_file(args.addr), args.addr, args.count):
        mark = ""
        if insn.name in ("jalr", "jr") and insn.rs != 31:
            mark = "   <-- indirect call"
        if insn.addr == 0x0884F890:
            mark += "   <-- the call site (RA-8)"
        body = insn.text() if callable(insn.text) else insn.text
        print(f"   0x{insn.addr:08x}  {body}{mark}")


if __name__ == "__main__":
    main()

"""Find every instruction that touches a given global, with context.

The font lives inside the decompressed stream1, whose base the game keeps in a global at
0x89F5DE4.  Whatever draws a glyph has to read that global and then scale an index into an
offset from it, so the instructions around each reference are where the glyph lookup will be
if it exists at all.

Addresses are formed in two halves on MIPS and the second half often hides in a load's offset,
so this carries lui values forward rather than looking for lui/addiu pairs.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mipsdis import disassemble

ROOT = Path(r"D:\psp\원격수사")
BOOT = ROOT / "iso_extract" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN"
LOADS = {"lw", "lh", "lhu", "lb", "lbu", "sw", "sh", "sb", "lwl", "lwr", "lwc1", "swc1"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=BOOT)
    parser.add_argument("--target", type=lambda v: int(v, 0), required=True)
    parser.add_argument("--window", type=int, default=4)
    parser.add_argument("--context", type=int, default=8)
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()

    listing, base, delta = disassemble(args.file)
    lo, hi = args.target, args.target + args.window
    upper, hits = {}, []
    for n, insn in enumerate(listing):
        name, ops = insn.mnemonic, insn.op_str
        parts = [p.strip() for p in ops.split(",")]
        if name == "lui":
            try:
                upper[parts[0]] = int(parts[1], 0) << 16
            except (ValueError, IndexError):
                upper.pop(parts[0] if parts else "", None)
            continue
        if name in ("addiu", "ori", "addi") and len(parts) == 3 and parts[1] in upper:
            try:
                value = int(parts[2], 0)
                if name != "ori" and value & 0x8000:
                    value -= 0x10000
                addr = (upper[parts[1]] + value) & 0xFFFFFFFF
                upper[parts[0]] = addr
                if lo <= addr < hi:
                    hits.append(n)
                continue
            except ValueError:
                pass
        if name in LOADS and "(" in ops:
            head, _, tail = ops.rpartition("(")
            reg = tail.rstrip(")")
            if reg in upper:
                try:
                    value = int(head.split(",")[-1].strip(), 0)
                    if value & 0x8000:
                        value -= 0x10000
                    if lo <= (upper[reg] + value) & 0xFFFFFFFF < hi:
                        hits.append(n)
                except ValueError:
                    pass
        if parts and parts[0].startswith("$"):
            upper.pop(parts[0], None)

    print(f"{len(hits)} instructions reach {lo:#x}..{hi:#x}\n")
    for n in hits[: args.limit]:
        a, b = max(0, n - args.context), min(len(listing), n + args.context + 1)
        print(f"--- {listing[n].address:#010x} (file {listing[n].address - delta:#x})")
        for insn in listing[a:b]:
            mark = ">>" if insn is listing[n] else "  "
            print(f"  {mark} {insn.address:#010x}  {insn.mnemonic:9s} {insn.op_str}")
        print()


if __name__ == "__main__":
    main()

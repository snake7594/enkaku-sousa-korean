"""Find every place the code indexes into a decompressed stream.

Trial and error kept pointing at plausible-but-wrong causes because it was testing guesses
instead of reading the loader.  This works from the executable end instead.

At 0x08843134 the decompressed buffer is stored into a table of 104-byte records based at
0x089E9EEC, indexed by a counter at 0x089E9EE0, with the buffer pointer at field 0.  So any
code that reaches into stream 1 must first load that field -- which makes the table the
single choke point through which every offset into the stream has to pass.

Listing the code that touches the table, and what each site adds to the pointer it loads,
enumerates the ways the game addresses the stream.  Anything that adds a value read from
elsewhere is a stored offset, and a stored offset that the patch does not rewrite is exactly
the failure being chased -- one that survives both growing and shrinking the text, as
observed.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

import mips
from find_dispatch import FILE_BASE, TEXT_SIZE, TEXT_VADDR

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")
TABLE = 0x089E9EEC
COUNTER = 0x089E9EE0
STRIDE = 104


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=lambda v: int(v, 0), default=TABLE)
    parser.add_argument("--span", type=int, default=0x40,
                        help="treat any global within this many bytes as the same table")
    parser.add_argument("--show", type=int, default=20)
    args = parser.parse_args()

    data = BOOT.read_bytes()
    insns = mips.disassemble(data, FILE_BASE, TEXT_VADDR, TEXT_SIZE // 4)

    # resolve lui/addiu and lui/lw pairs into the global they address
    upper: dict[int, int] = {}
    sites = []
    for i, insn in enumerate(insns):
        if insn.name == "lui":
            upper[insn.rt] = insn.imm << 16
        elif insn.rs in upper and insn.name in ("addiu", "lw", "lh", "lhu", "lb", "lbu", "sw"):
            target = upper[insn.rs] + mips.signed(insn.imm)
            if abs(target - args.base) <= args.span or abs(target - COUNTER) <= args.span:
                sites.append((i, insn, target))

    print(f"{len(sites)} instructions address the resource table "
          f"(0x{args.base:08x} +/- 0x{args.span:x})\n")

    by_global = Counter(t for _, _, t in sites)
    for target, count in sorted(by_global.items()):
        role = ("counter" if abs(target - COUNTER) < 4 else
                f"table+{target - args.base}" if target >= args.base else
                f"table{target - args.base}")
        print(f"   0x{target:08x}  {count:4d} uses   {role}")

    # for the sites that LOAD the buffer pointer, what gets added to it?
    print(f"\nwhat is added to a loaded buffer pointer:")
    adds = defaultdict(int)
    examples = defaultdict(list)
    for i, insn, target in sites:
        if insn.name != "lw":
            continue
        reg = insn.rt
        for j in range(i + 1, min(i + 12, len(insns))):
            nxt = insns[j]
            if nxt.name == "addu" and reg in (nxt.rs, nxt.rt):
                other = nxt.rt if nxt.rs == reg else nxt.rs
                # where did the added value come from?
                src = "unknown"
                for k in range(max(0, j - 10), j):
                    prev = insns[k]
                    if prev.rt == other and prev.name in ("lw", "lh", "lhu", "lbu", "lb"):
                        src = f"loaded ({prev.name})"
                    elif prev.rt == other and prev.name in ("sll", "addiu", "addu"):
                        src = "computed"
                adds[src] += 1
                examples[src].append(insn.addr)
                break
            if nxt.rt == reg and nxt.name in ("lw", "addiu", "lui"):
                break

    for src, count in sorted(adds.items(), key=lambda kv: -kv[1]):
        where = ", ".join(f"0x{a:08x}" for a in examples[src][:4])
        print(f"   {src:18s} {count:4d} sites   {where}")


if __name__ == "__main__":
    main()

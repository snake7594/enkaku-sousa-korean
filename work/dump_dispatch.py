"""Dump a dispatch-table candidate and the byte table that follows it.

If the byte table really is operand sizes indexed by opcode, its values must agree with
the instruction lengths already established by reading the bytecode: 0x01 and 0x0E take
a 32-bit operand, 0x00 and 0x14 take none.  That cross-check is what turns a plausible
looking array into a usable length table.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from find_dispatch import to_vaddr

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")

# lengths inferred from walking the bytecode (total instruction size, opcode included)
OBSERVED = {0x00: 1, 0x01: 5, 0x0E: 5, 0x14: 1}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", type=lambda v: int(v, 0), default=0x089A18)
    parser.add_argument("--entries", type=int, default=89)
    parser.add_argument("--bytes", type=int, default=96)
    args = parser.parse_args()

    data = BOOT.read_bytes()

    print(f"dispatch table at file 0x{args.table:x} (vaddr 0x{to_vaddr(args.table):08x})")
    handlers = []
    for i in range(args.entries):
        value = struct.unpack_from("<I", data, args.table + i * 4)[0]
        handlers.append(value)
    unique = {}
    for i, h in enumerate(handlers):
        unique.setdefault(h, []).append(i)
    print(f"   {len(handlers)} entries, {len(unique)} distinct handlers")
    for h in sorted(unique)[:12]:
        ops = unique[h]
        shown = ", ".join(f"{o:02x}" for o in ops[:10])
        print(f"   0x{h:08x}  opcodes {shown}{' ...' if len(ops) > 10 else ''}")

    after = args.table + args.entries * 4
    table = data[after : after + args.bytes]
    print(f"\nbyte table at file 0x{after:x} (vaddr 0x{to_vaddr(after):08x}):")
    for row in range(0, len(table), 16):
        chunk = table[row : row + 16]
        print(f"   {row:02x}: " + " ".join(f"{b:02x}" for b in chunk))

    print("\ncross-check against lengths observed in the bytecode:")
    ok = bad = 0
    for opcode, total in sorted(OBSERVED.items()):
        if opcode >= len(table):
            continue
        value = table[opcode]
        for label, expected in (("operand only", total - 1), ("whole instruction", total)):
            if value == expected:
                print(f"   opcode {opcode:02x}: table says {value} = {label} ({total} total)  OK")
                ok += 1
                break
        else:
            print(f"   opcode {opcode:02x}: table says {value}, expected {total - 1} or {total}  MISMATCH")
            bad += 1
    print(f"\n{ok} agree, {bad} disagree")


if __name__ == "__main__":
    main()

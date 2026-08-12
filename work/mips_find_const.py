"""Look for the arithmetic that turns a byte pair into a glyph, rather than for the strings.

Chasing the string table stalled: nothing in the code forms its address, so it is reached some
way this crude tracker does not follow.  The glyph lookup is easier to recognise, because it
has to do a specific sum.  The script's encoding is index = (lead - 0x88) * 253 + trail, and
253 is an unusual constant to find in a binary.

The multiply may not survive as a multiply -- 253 is 256 - 3, and compilers like to emit that
as shifts and subtracts -- so this reports both: any instruction carrying the constant, and any
`mul`/`mult` at all, with a little context around each.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from capstone import CS_ARCH_MIPS, CS_MODE_32, CS_MODE_LITTLE_ENDIAN, Cs

ROOT = Path(r"D:\psp\원격수사")
BOOT = ROOT / "iso_extract" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=BOOT)
    parser.add_argument("--values", type=lambda v: [int(x, 0) for x in v.split(",")],
                        default=[253, 0x88, 0x8D])
    parser.add_argument("--context", type=int, default=3)
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    blob = args.file.read_bytes()
    phoff, = struct.unpack_from("<I", blob, 28)
    p_offset, p_vaddr, _, p_filesz = struct.unpack_from("<4I", blob, phoff + 4)
    md = Cs(CS_ARCH_MIPS, CS_MODE_32 | CS_MODE_LITTLE_ENDIAN)

    listing = list(md.disasm(blob[p_offset:p_offset + p_filesz], p_vaddr))
    print(f"{len(listing)} instructions disassembled from {p_vaddr:#x}")
    index = {insn.address: n for n, insn in enumerate(listing)}

    wanted = set(args.values)
    hits = []
    for n, insn in enumerate(listing):
        for token in insn.op_str.replace(",", " ").split():
            if token.startswith("$") or "(" in token:
                continue
            try:
                value = int(token, 0)
            except ValueError:
                continue
            if value in wanted:
                hits.append((n, value))
                break

    # only interesting when 253 shows up near a byte-pair test
    by_value = {}
    for n, value in hits:
        by_value.setdefault(value, []).append(n)
    for value, places in sorted(by_value.items()):
        print(f"\nconstant {value:#x} ({value}): {len(places)} instructions")
        for n in places[: args.limit]:
            lo = max(0, n - args.context)
            hi = min(len(listing), n + args.context + 1)
            print(f"   --- around {listing[n].address:#010x}")
            for insn in listing[lo:hi]:
                mark = ">>" if insn.address == listing[n].address else "  "
                print(f"   {mark} {insn.address:#010x}  {insn.mnemonic:8s} {insn.op_str}")


if __name__ == "__main__":
    main()

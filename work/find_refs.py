"""Find what refers to a string in BOOT.BIN, by address and by lui/addiu pair.

BOOT.BIN is a plain MIPS ELF with one PT_LOAD: file offset 0x54 maps to virtual 0x8804000, so
a file offset converts to an address by adding 0x8803FAC.  The save menu's セーブ sits at file
offset 0x103708, which is address 0x89076B4.

Two ways to reach a string on MIPS, and this looks for both.  A pointer table stores the
address as a word.  Code builds it with `lui reg, hi` followed by `addiu reg, reg, lo`, where
lo is signed -- so hi is (addr >> 16) plus one when the low half has its top bit set.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
BOOT = ROOT / "iso_extract" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN"


def load(path: Path):
    blob = path.read_bytes()
    phoff, = struct.unpack_from("<I", blob, 28)
    p_offset, p_vaddr, _, p_filesz = struct.unpack_from("<4I", blob, phoff + 4)
    return blob, p_vaddr - p_offset, p_offset, p_filesz


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=BOOT)
    parser.add_argument("--offset", type=lambda v: int(v, 0), default=0x103708,
                        help="file offset of the target")
    parser.add_argument("--window", type=int, default=64,
                        help="also match addresses this far after the target")
    args = parser.parse_args()

    blob, delta, p_offset, p_filesz = load(args.file)
    target = args.offset + delta
    print(f"{args.file.name}: file+{delta:#x} -> vaddr; "
          f"segment {p_offset:#x}..{p_offset + p_filesz:#x}")
    print(f"target file {args.offset:#x} = vaddr {target:#x}\n")

    words = []
    for i in range(0, len(blob) - 3, 4):
        value = int.from_bytes(blob[i:i + 4], "little")
        if target <= value < target + args.window:
            words.append((i, value))
    print(f"{len(words)} word-aligned pointers into the target range")
    for at, value in words[:20]:
        print(f"   pointer at file {at:#x} (vaddr {at + delta:#x}) -> {value:#x}")

    hi, lo = target >> 16, target & 0xFFFF
    if lo & 0x8000:
        hi += 1
    print(f"\nlooking for lui with {hi:#06x} then addiu with {lo:#06x} "
          f"(or ori, or a nearby lo)")
    luis = []
    for i in range(0, len(blob) - 3, 4):
        word = int.from_bytes(blob[i:i + 4], "little")
        if (word >> 26) == 0x0F and (word & 0xFFFF) == hi:      # lui rt, hi
            luis.append((i, (word >> 16) & 0x1F))
    print(f"{len(luis)} lui instructions carrying {hi:#06x}")

    pairs = []
    for at, rt in luis:
        for step in range(1, 12):
            j = at + step * 4
            if j + 4 > len(blob):
                break
            word = int.from_bytes(blob[j:j + 4], "little")
            op, rs, rd, imm = word >> 26, (word >> 21) & 0x1F, (word >> 16) & 0x1F, word & 0xFFFF
            if op in (0x09, 0x0D) and rs == rt:                 # addiu / ori from that reg
                if target <= (hi << 16) + (imm - 0x10000 if imm & 0x8000 else imm) < target + args.window:
                    pairs.append((at, j, rt, imm))
                break
            if op == 0x0F and rd == rt:                          # overwritten by another lui
                break
    print(f"{len(pairs)} lui/addiu pairs land in the target range")
    for a, b, rt, imm in pairs[:20]:
        print(f"   lui at file {a:#x} (vaddr {a + delta:#x}), low half at {b:#x}, "
              f"reg ${rt}, imm {imm:#06x}")


if __name__ == "__main__":
    main()

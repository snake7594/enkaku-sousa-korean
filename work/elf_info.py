"""Parse the PSP module's ELF headers.

Finding the interpreter's dispatch table means recognising an array of code pointers,
which first requires knowing where code actually lives in the module's address space —
file offsets and virtual addresses differ, and a pointer array is only recognisable
once its values can be checked against the real .text range.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")

SH_TYPES = {0: "NULL", 1: "PROGBITS", 2: "SYMTAB", 3: "STRTAB", 8: "NOBITS", 9: "REL"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=BOOT)
    args = parser.parse_args()

    data = args.path.read_bytes()
    if data[:4] != b"\x7fELF":
        raise SystemExit("not an ELF")

    (e_type, e_machine, _ver, e_entry, e_phoff, e_shoff, e_flags,
     e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum,
     e_shstrndx) = struct.unpack_from("<HHIIIIIHHHHHH", data, 16)
    print(f"type {e_type}  machine {e_machine} (8 = MIPS)  entry 0x{e_entry:08x}")
    print(f"{e_phnum} program headers, {e_shnum} sections")

    print("\nprogram headers:")
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = \
            struct.unpack_from("<IIIIIIII", data, off)
        print(f"   [{i}] type {p_type} off 0x{p_offset:06x} vaddr 0x{p_vaddr:08x} "
              f"filesz 0x{p_filesz:06x} memsz 0x{p_memsz:06x} flags {p_flags}")

    # section names
    sh = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        sh.append(struct.unpack_from("<IIIIIIIIII", data, off))
    strtab_off = sh[e_shstrndx][4]

    def name_of(index: int) -> str:
        end = data.index(b"\0", strtab_off + index)
        return data[strtab_off + index : end].decode("ascii", "replace")

    print("\nsections:")
    for i, (s_name, s_type, s_flags, s_addr, s_offset, s_size, *_rest) in enumerate(sh):
        if not s_size:
            continue
        kind = SH_TYPES.get(s_type, str(s_type))
        print(f"   {name_of(s_name):24s} {kind:9s} addr 0x{s_addr:08x} "
              f"off 0x{s_offset:06x} size 0x{s_size:06x}")


if __name__ == "__main__":
    main()

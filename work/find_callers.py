"""Find every `jal` to a given address.

The text routine at 0x0884CAC4 is called from wherever the engine decides a text block
needs drawing or measuring — which is the script-level code we are looking for.  Walking
up the call graph is a far more direct route to it than pattern-matching on bytes.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import mips
from find_dispatch import FILE_BASE, TEXT_SIZE, TEXT_VADDR

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")


def function_start(insns: list[mips.Insn], index: int) -> int:
    """Walk back to the previous `jr $ra` + delay slot, i.e. the start of this function."""
    for i in range(index, max(0, index - 3000), -1):
        if insns[i].name == "jr" and insns[i].rs == 31:
            return i + 2
    return max(0, index - 3000)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=lambda v: int(v, 0), required=True)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    data = BOOT.read_bytes()
    insns = mips.disassemble(data, FILE_BASE, TEXT_VADDR, TEXT_SIZE // 4)

    callers = []
    for i, insn in enumerate(insns):
        if insn.name == "jal" and insn.target == args.target:
            start = function_start(insns, i)
            callers.append((insn.addr, insns[start].addr, i - start))

    print(f"{len(callers)} call sites to 0x{args.target:08x}\n")
    for site, func, offset in callers[: args.top]:
        print(f"   call at 0x{site:08x}   inside function 0x{func:08x} (+{offset} insns)")

    funcs = {}
    for _, func, _ in callers:
        funcs[func] = funcs.get(func, 0) + 1
    print(f"\n{len(funcs)} distinct calling functions:")
    for func, count in sorted(funcs.items(), key=lambda kv: -kv[1]):
        print(f"   0x{func:08x}  {count} call(s)")


if __name__ == "__main__":
    main()

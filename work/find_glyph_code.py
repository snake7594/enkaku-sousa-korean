"""Find the code that turns a text byte pair into a glyph.

The script's encoding is index = (lead - 0x88) * 253 + trail, and the menu text uses the same
byte layout, so whatever draws it has to do that sum somewhere.  253 is a distinctive constant
-- distinctive enough to find by scanning -- and where it appears, the surrounding instructions
should show the lead byte being biased by 0x88 and the result being scaled into a glyph
address.

The comparison against 0x88 and 0x8D is worth looking for on its own: the reader has to decide
whether a byte begins a two-byte kanji, and that test is a bounds check against exactly those
values.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mipsdis import disassemble

ROOT = Path(r"D:\psp\원격수사")
BOOT = ROOT / "iso_extract" / "PSP_GAME" / "SYSDIR" / "BOOT.BIN"


def literals(insn):
    for token in insn.op_str.replace(",", " ").replace("(", " ").replace(")", " ").split():
        if token.startswith("$"):
            continue
        try:
            yield int(token, 0)
        except ValueError:
            continue


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=BOOT)
    parser.add_argument("--values", default="253")
    parser.add_argument("--context", type=int, default=6)
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()

    wanted = {int(v, 0) for v in args.values.split(",")}
    listing, base, delta = disassemble(args.file)
    print(f"{len(listing)} instructions from {base:#x}\n")

    hits = [n for n, insn in enumerate(listing)
            if insn.mnemonic != ".word" and wanted & set(literals(insn))]
    print(f"{len(hits)} instructions carry one of {sorted(wanted)}")
    for n in hits[: args.limit]:
        lo, hi = max(0, n - args.context), min(len(listing), n + args.context + 1)
        print(f"\n--- {listing[n].address:#010x} (file {listing[n].address - delta:#x})")
        for insn in listing[lo:hi]:
            mark = ">>" if insn is listing[n] else "  "
            print(f"  {mark} {insn.address:#010x}  {insn.mnemonic:9s} {insn.op_str}")


if __name__ == "__main__":
    main()

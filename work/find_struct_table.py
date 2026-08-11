"""Look for an opcode table laid out as a struct array rather than bare pointers.

The plain-pointer scan found only small compiler switches, and the MIPS jump-table idiom
turned up nothing interpreter-sized.  A common alternative is one record per opcode —
handler pointer plus operand size and flags — which a stride-4 scan cannot see.

Any hit is checked against the instruction lengths already read out of the bytecode,
because a length field is the whole reason to care about this table.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from find_dispatch import TEXT_SIZE, TEXT_VADDR, to_vaddr

BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")

# total instruction size, opcode byte included, as walked in the script
OBSERVED = {0x00: 1, 0x01: 5, 0x0E: 5, 0x14: 1}


def is_handler(value: int) -> bool:
    return TEXT_VADDR <= value < TEXT_VADDR + TEXT_SIZE and value % 4 == 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strides", default="8,12,16,20,24")
    parser.add_argument("--min-run", type=int, default=24)
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()

    data = BOOT.read_bytes()
    results = []

    for stride in (int(s) for s in args.strides.split(",")):
        for slot in range(0, stride, 4):
            off = slot
            while off + stride * args.min_run < len(data):
                run = 0
                while True:
                    pos = off + run * stride
                    if pos + 4 > len(data):
                        break
                    value = struct.unpack_from("<I", data, pos)[0]
                    if not is_handler(value):
                        break
                    run += 1
                if run >= args.min_run:
                    results.append((run, stride, slot, off))
                    off += run * stride
                else:
                    off += stride
    results.sort(reverse=True)

    print(f"{len(results)} struct-shaped runs found")
    for run, stride, slot, off in results[: args.top]:
        print(f"\n   stride {stride}, pointer at +{slot}, file 0x{off:06x} "
              f"(vaddr 0x{to_vaddr(off):08x}), {run} records")
        record = data[off - slot : off - slot + stride]
        print("      first record: " + " ".join(f"{b:02x}" for b in record))
        # does any byte position in the record match the known lengths?
        for pos in range(stride):
            if pos // 4 * 4 == slot:
                continue
            values = {}
            ok = True
            for opcode, total in OBSERVED.items():
                idx = off - slot + opcode * stride + pos
                if idx >= len(data):
                    ok = False
                    break
                values[opcode] = data[idx]
            if not ok:
                continue
            if all(values[o] in (t, t - 1) for o, t in OBSERVED.items()):
                print(f"      byte +{pos} matches the observed lengths: {values}  <== length field")


if __name__ == "__main__":
    main()

"""Learn the bytecode's instruction lengths so the stream can be walked reliably.

Relocating inline text means every absolute reference has to be found and rewritten,
and the only way to be confident none were missed is to decode instruction boundaries
rather than pattern-match on bytes.  This surveys what follows each opcode so a length
table can be built from evidence.

Pointer targets are a strong signal: if the length model is right, the addresses stored
in `01 <u32>` operands should land exactly on instruction boundaries.
"""

from __future__ import annotations

import argparse
import struct
from collections import Counter, defaultdict
from pathlib import Path

import lzss
from extract_all_text import TEXT_START, find_runs

SRC = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR\0000")
STREAM1 = 0x27E000


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=lambda v: int(v, 0), default=TEXT_START)
    parser.add_argument("--samples", type=int, default=6)
    args = parser.parse_args()

    plain = lzss.decompress(SRC.read_bytes(), STREAM1)[0]
    runs = find_runs(plain, TEXT_START, min_tokens=3, min_wide=1)
    text_spans = [(offset, offset + len(t)) for offset, t in
                  ((o, _raw_len(plain, o)) for o, _ in runs)]
    in_text = bytearray(len(plain))
    for a, b in text_spans:
        for i in range(a, min(b, len(plain))):
            in_text[i] = 1
    print(f"{len(runs)} text runs cover {sum(in_text)} of {len(plain) - args.start} bytecode bytes")

    # what byte follows each opcode, outside text
    following = defaultdict(Counter)
    opcodes = Counter()
    i = args.start
    while i < len(plain) - 8:
        if in_text[i]:
            i += 1
            continue
        b = plain[i]
        opcodes[b] += 1
        following[b][plain[i + 1]] += 1
        i += 1

    print("\nmost common bytes outside text, and what follows them:")
    for op, count in opcodes.most_common(16):
        nxt = following[op].most_common(3)
        pretty = " ".join(f"{v:02x}:{n * 100 // count}%" for v, n in nxt)
        print(f"   {op:02x}  {count:7d}   next: {pretty}")

    # where do 01 <u32> operands point?
    targets = []
    i = args.start
    while i + 5 <= len(plain):
        if not in_text[i] and plain[i] == 0x01:
            value = struct.unpack_from("<I", plain, i + 1)[0]
            if 0 < value < len(plain):
                targets.append(value)
            i += 5
            continue
        i += 1
    print(f"\n{len(targets)} pointer targets")
    kinds = Counter("inside text" if in_text[t] else "outside text" for t in targets)
    print(f"   {dict(kinds)}")
    print(f"   distinct targets: {len(set(targets))}")
    lo, hi = min(targets), max(targets)
    print(f"   range 0x{lo:x}-0x{hi:x}")

    print("\nbytes at a few pointer targets:")
    for t in sorted(set(targets))[: args.samples]:
        print(f"   0x{t:08x}  " + " ".join(f"{x:02x}" for x in plain[t : t + 12]))


def _raw_len(plain: bytes, offset: int) -> str:
    """Re-derive a run's byte length using the extractor's own walk."""
    from extract_all_text import find_runs as _fr
    sub = _fr(plain[offset : offset + 4096], 0, 1, 0)
    return "x" * (sub[0][0] if False else _span(plain, offset))


def _span(plain: bytes, offset: int) -> int:
    from decode_script import HIRA, HIRA_BASE, LEAD_HI, LEAD_LO
    end = offset
    n = len(plain)
    while end < n:
        b = plain[end]
        if b == 0x0F:
            end += 2 if (end + 1 < n and 0x31 <= plain[end + 1] <= 0x39) else 1
        elif b == 0x11:
            end += 1
        elif b == 0x16:
            end += 2
        elif LEAD_LO <= b <= LEAD_HI:
            end += 2
        elif HIRA_BASE <= b < HIRA_BASE + len(HIRA) or 0xA1 <= b <= 0xDF:
            end += 1
        else:
            break
    return end - offset


if __name__ == "__main__":
    main()

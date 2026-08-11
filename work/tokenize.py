"""Tokenise the 원격수사 script text region and histogram the codes.

The punctuation seen in the stream (0x8140 space, 0x8141 、, 0x8142 。, 0x8148 ？,
0x8163 …, 0x8179 【, 0x817A 】) is genuine Shift-JIS, so the stream is at least
SJIS-shaped: a lead byte in the 0x81.. range starts a two-byte code.  This tool
tokenises on that assumption and reports what the codes actually look like, which
is what tells us how the kanji block was remapped.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

STREAM = Path(r"D:\psp\원격수사\font_extract\script_stream.bin")
TEXT_START = 0x3AC80
TEXT_END = 0x15AC80


def tokenize(data: bytes, lead_lo: int, lead_hi: int) -> list[int]:
    codes = []
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if lead_lo <= b <= lead_hi and i + 1 < n:
            codes.append((b << 8) | data[i + 1])
            i += 2
        else:
            codes.append(b)
            i += 1
    return codes


def sjis(code: int) -> str:
    try:
        return bytes([code >> 8, code & 0xFF]).decode("cp932")
    except Exception:  # noqa: BLE001
        return ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=lambda v: int(v, 0), default=TEXT_START)
    parser.add_argument("--end", type=lambda v: int(v, 0), default=TEXT_END)
    parser.add_argument("--lead-lo", type=lambda v: int(v, 0), default=0x81)
    parser.add_argument("--lead-hi", type=lambda v: int(v, 0), default=0xEF)
    parser.add_argument("--top", type=int, default=48)
    args = parser.parse_args()

    data = STREAM.read_bytes()[args.start : args.end]
    codes = tokenize(data, args.lead_lo, args.lead_hi)
    single = [c for c in codes if c < 0x100]
    double = [c for c in codes if c >= 0x100]
    print(f"{len(codes)} tokens: {len(single)} single-byte, {len(double)} two-byte")

    leads = Counter(c >> 8 for c in double)
    print("\nlead byte distribution:")
    for lead, count in sorted(leads.items()):
        print(f"   0x{lead:02x}: {count:7d}")

    trails = Counter(c & 0xFF for c in double)
    lo = min(trails), max(trails)
    print(f"\ntrail byte range: 0x{lo[0]:02x}-0x{lo[1]:02x}, distinct {len(trails)}")

    print(f"\ntop {args.top} two-byte codes (cp932 column = what real Shift-JIS would give):")
    for code, count in Counter(double).most_common(args.top):
        print(f"   {code:04x}  {count:6d}   {sjis(code)}")

    print(f"\ntop 24 single-byte codes:")
    for code, count in Counter(single).most_common(24):
        printable = chr(code) if 0x20 <= code < 0x7F else "."
        print(f"   {code:02x}  {count:6d}   {printable}")


if __name__ == "__main__":
    main()

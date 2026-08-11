"""Map which bytes of an archive are accounted for by LZ11 streams, and report the gaps.

Anything large that is not inside a compressed stream is raw data — a font table
would show up exactly there.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import lzss

ROOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR")

KNOWN_MAGIC = {
    b"SGXD": "SGXD sound bank",
    b"PSMF": "PSMF movie",
    b"RIFF": "RIFF",
    b"\x89PNG": "PNG",
    b"MIG.": "GIM texture",
    b"VSTD": "SGXD VSTD",
    b"RGND": "SGXD RGND",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="+")
    parser.add_argument("--min-gap", type=lambda v: int(v, 0), default=0x1000)
    parser.add_argument("--align", type=lambda v: int(v, 0), default=0x800)
    args = parser.parse_args()

    for name in args.names:
        data = (ROOT / name).read_bytes()
        covered = bytearray(len(data))
        streams = 0
        for base in range(0, len(data) - 8, args.align):
            for delta in (0x00, 0x40):
                pos = base + delta
                if pos + 8 > len(data) or data[pos] != 0x11:
                    continue
                declared = int.from_bytes(data[pos + 1 : pos + 4], "little")
                if not (0x100 <= declared <= 0x4000000):
                    continue
                result = lzss.try_decompress(data, pos, limit=0x4000000)
                if result is None:
                    continue
                _, consumed = result
                for i in range(base, min(pos + consumed, len(data))):
                    covered[i] = 1
                streams += 1
                break

        gaps = []
        start = None
        for i, flag in enumerate(covered):
            if not flag and start is None:
                start = i
            elif flag and start is not None:
                gaps.append((start, i))
                start = None
        if start is not None:
            gaps.append((start, len(covered)))

        big = [(a, b) for a, b in gaps if b - a >= args.min_gap]
        uncovered = sum(b - a for a, b in gaps)
        print(f"== {name}: 0x{len(data):x} bytes, {streams} streams, "
              f"uncovered 0x{uncovered:x} ({uncovered * 100 / len(data):.1f}%), {len(big)} gaps >= 0x{args.min_gap:x}")
        for a, b in big[:20]:
            # skip pure padding
            chunk = data[a : min(a + 0x2000, b)]
            if not any(chunk):
                kind = "zero padding"
            else:
                kind = "raw?"
                for magic, label in KNOWN_MAGIC.items():
                    idx = data.find(magic, a, min(a + 0x1000, b))
                    if idx >= 0:
                        kind = f"{label} @0x{idx:x}"
                        break
            head = " ".join(f"{x:02x}" for x in data[a : a + 16])
            print(f"   0x{a:08x}-0x{b:08x}  0x{b - a:<8x} {kind:<24s} {head}")
        print()


if __name__ == "__main__":
    main()

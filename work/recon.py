"""First-pass recon over the extracted USRDIR archives: headers, entropy, magics."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR")

MAGICS = {
    b"PGF0": "PSP PGF font",
    b"BGFO": "PSP BWFON",
    b"MIG.": "GIM texture",
    b"\x89PNG": "PNG",
    b"GMO ": "GMO model",
    b"\x00PSP": "PSP prx",
    b"~PSP": "encrypted prx",
    b"\x7fELF": "ELF",
    b"RIFF": "RIFF",
    b"OMG.": "AT3",
}


def hexdump(data: bytes, length: int = 64) -> str:
    return " ".join(f"{b:02x}" for b in data[:length])


def main() -> None:
    for path in sorted(ROOT.glob("00*")):
        size = path.stat().st_size
        with path.open("rb") as fh:
            head = fh.read(0x80)
            fh.seek(max(0, size - 0x40))
            tail = fh.read(0x40)
        print(f"== {path.name}  size={size} (0x{size:x})")
        print(f"   head {hexdump(head, 48)}")
        print(f"   tail {hexdump(tail, 32)}")
        # LZ11-style header check: 0x11 + 24-bit LE size
        if head[0] == 0x11:
            declared = int.from_bytes(head[1:4], "little")
            print(f"   LZ11? declared decompressed size = {declared} (0x{declared:x})")
        print()


if __name__ == "__main__":
    main()

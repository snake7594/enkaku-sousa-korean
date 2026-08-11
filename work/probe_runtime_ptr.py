"""Check the runtime script pointer against the stream, using values read from the emulator.

The memory viewer gave two numbers on a healthy title screen:

    0x089F5DE4 = 0x090FB88C   the stream 1 buffer
    0x089F62A4 = 0x09132ECA   the script pointer

so the interpreter was sitting at stream offset 0x3763E.  That is a fact about the running
game rather than an inference, which makes it the first chance to test the parse model
against the engine: the byte there must be a valid opcode (0x00-0x1C), and the position must
be one the parse actually visits.
"""

from __future__ import annotations

import struct
from pathlib import Path

import lzss
import opcodes
import text_blocks

BASE = 0x090FB88C
POINTER = 0x09132ECA
ARCHIVE = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR\0000")


def main() -> None:
    plain = lzss.decompress(ARCHIVE.read_bytes(), 0x27E000)[0]
    off = POINTER - BASE
    print(f"stream {len(plain)} bytes; runtime offset 0x{off:06x} ({off})")
    print(f"   in range: {0 <= off < len(plain)}")
    print(f"   byte there: 0x{plain[off]:02x} "
          f"({'valid opcode' if plain[off] <= 0x1C else 'NOT a valid opcode'})")
    print(f"   bytes:  {plain[off:off + 24].hex(' ')}")
    print(f"   before: {plain[max(0, off - 16):off].hex(' ')}")

    header = struct.unpack_from("<8I", plain, 0)
    print(f"\nheader: {[hex(h) for h in header]}")
    for i, h in enumerate(header):
        if h and abs(off - h) < 0x2000:
            print(f"   offset is 0x{off - h:x} past header[{i}] = 0x{h:x}")

    blocks = text_blocks.find_blocks(plain)
    flags = opcodes.text_flags(plain, blocks)
    seen = {p for p, _, _ in opcodes.parse(plain, 0x02AC80, len(plain), flags)}
    print(f"\nparse visits {len(seen)} positions")
    print(f"   is the runtime offset one of them? {off in seen}")
    near = sorted(x for x in seen if abs(x - off) <= 12)
    print(f"   nearby parse boundaries: {[hex(x) for x in near]}")


if __name__ == "__main__":
    main()

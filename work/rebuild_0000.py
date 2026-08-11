"""Losslessly rebuild USRDIR/0000 by re-compressing its two LZ11 streams.

Layout of this archive (it does not use the 0x40 MD5 block header the other archives
have — both streams sit raw at 0x800-aligned offsets):

    0x000000  LZ11 stream 0   (UI textures)      followed by zero padding
    0x1B7000  SGXD sound bank                    left byte-for-byte alone
    0x27E000  LZ11 stream 1   (font + script)    followed by an unidentified blob

The re-compressed streams are smaller than the originals, so everything keeps its
original offset and the file keeps its original size — which means the ISO can be
patched in place with no directory changes at all.  Anything not deliberately
rewritten is copied through unchanged, including that trailing blob, whose purpose
is still unknown.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import lz11_compress
import lzss

SRC = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR\0000")

STREAM0 = 0x000000
SGXD_START = 0x1B7000
STREAM1 = 0x27E000


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--chain", type=int, default=64)
    parser.add_argument("--src", type=Path, default=SRC)
    parser.add_argument("--plain0", type=Path, default=None,
                        help="replacement contents for stream 0 (UI textures)")
    parser.add_argument("--plain1", type=Path, default=None,
                        help="replacement contents for stream 1 (font + script)")
    args = parser.parse_args()

    original = args.src.read_bytes()
    print(f"source: {args.src.name}  0x{len(original):x} bytes")

    plain0, packed0_len = lzss.decompress(original, STREAM0)
    plain1, packed1_len = lzss.decompress(original, STREAM1)
    if args.plain0:
        replacement = args.plain0.read_bytes()
        if len(replacement) != len(plain0):
            raise SystemExit(
                f"--plain0 must keep the stream's size ({len(plain0)}), "
                f"got {len(replacement)}")
        print(f"   stream0 contents replaced from {args.plain0.name}")
        plain0 = replacement
    if args.plain1:
        replacement = args.plain1.read_bytes()
        # the decompressed stream may now be larger -- Korean text costs 140% of Japanese.
        # What has to fit is the *packed* size, and that is checked below against the
        # trailing blob, so the uncompressed length is free to change.
        print(f"   stream1 contents replaced from {args.plain1.name} "
              f"({len(replacement) - len(plain1):+d} bytes decompressed)")
        plain1 = replacement
    tail_start = STREAM1 + packed1_len
    print(f"   stream0 packed 0x{packed0_len:x} -> plain 0x{len(plain0):x}")
    print(f"   stream1 packed 0x{packed1_len:x} -> plain 0x{len(plain1):x}")
    print(f"   trailing blob 0x{tail_start:x}-0x{len(original):x} "
          f"({len(original) - tail_start} bytes) preserved as-is")

    print("compressing stream 0 ...")
    new0 = lz11_compress.compress(plain0, max_chain=args.chain)
    print(f"   0x{packed0_len:x} -> 0x{len(new0):x}")
    print("compressing stream 1 ...")
    new1 = lz11_compress.compress(plain1, max_chain=args.chain)
    print(f"   0x{packed1_len:x} -> 0x{len(new1):x}")

    if STREAM0 + len(new0) > SGXD_START:
        raise SystemExit("stream 0 no longer fits before the sound bank")
    if STREAM1 + len(new1) > tail_start:
        raise SystemExit("stream 1 no longer fits before the trailing blob")

    out = bytearray(len(original))
    out[STREAM0 : STREAM0 + len(new0)] = new0
    out[SGXD_START:STREAM1] = original[SGXD_START:STREAM1]
    out[STREAM1 : STREAM1 + len(new1)] = new1
    out[tail_start:] = original[tail_start:]
    rebuilt = bytes(out)

    # verification: same size, same decompressed content, untouched regions intact
    checks = {
        "size unchanged": len(rebuilt) == len(original),
        "stream 0 decompresses identically": lzss.decompress(rebuilt, STREAM0)[0] == plain0,
        "stream 1 decompresses identically": lzss.decompress(rebuilt, STREAM1)[0] == plain1,
        "sound bank untouched": rebuilt[SGXD_START:STREAM1] == original[SGXD_START:STREAM1],
        "trailing blob untouched": rebuilt[tail_start:] == original[tail_start:],
    }
    print()
    for label, ok in checks.items():
        print(f"   {'OK  ' if ok else 'FAIL'} {label}")
    if not all(checks.values()):
        raise SystemExit("verification failed")

    args.out.write_bytes(rebuilt)
    same = sum(1 for a, b in zip(rebuilt, original) if a == b)
    print(f"\n-> {args.out}")
    print(f"   {same}/{len(original)} bytes identical to the original "
          f"({same * 100 / len(original):.1f}%)")


if __name__ == "__main__":
    main()

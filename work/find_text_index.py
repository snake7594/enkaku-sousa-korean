"""Search every file for the dialogue index, allowing for how it might be encoded.

STEP1 proves the game locates each line correctly at its original offset, so a table of
those offsets exists somewhere.  The earlier sweep looked only for absolute little-endian
u32s equal to a run start and found nothing above chance -- which rules out that one
encoding, not the table.

An offset can be written down several ways, and each is cheap to test against the same
ground truth of 7,841 known run starts:

  absolute            the value is the stream offset
  relative to script  the value is offset - 0x02AC80, which is what a loader that keeps the
                      font and the script as separate regions would store
  relative to font    offset - 0x80
  halved / scaled     some engines store word counts rather than byte counts
  big-endian          the archive's block headers are big-endian, so the tooling might be
  sequential index    the value is the line number, 0..7840

Anything that lights up is the table the reflow has to rewrite; if none does, the dialogue
is not addressed by a stored offset at all and the whole approach needs rethinking rather
than another variant.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

import lzss
import text_blocks

ARCHIVE = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR\0000")
BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")
TSV = Path(r"D:\psp\원격수사\build\translation_ko.tsv")
SCRIPT_START = 0x02AC80


def u32(data: bytes, big: bool) -> np.ndarray:
    raw = np.frombuffer(data, dtype=np.uint8).astype(np.uint32)
    if big:
        return (raw[:-3] << 24) | (raw[1:-2] << 16) | (raw[2:-1] << 8) | raw[3:]
    return raw[:-3] | (raw[1:-2] << 8) | (raw[2:-1] << 16) | (raw[3:] << 24)


def score(values: np.ndarray, wanted: set[int], span: int) -> tuple[int, float]:
    if not len(values):
        return 0, 0.0
    lookup = np.zeros(span + 1, dtype=bool)
    keep = np.fromiter((w for w in wanted if 0 <= w <= span), dtype=np.int64)
    if not keep.size:
        return 0, 0.0
    lookup[keep] = True
    safe = np.minimum(values, span)
    hits = int(np.sum(lookup[safe] & (values <= span)))
    expected = len(values) * keep.size / (span + 1)
    return hits, hits / max(expected, 1e-9)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-ratio", type=float, default=4.0)
    args = parser.parse_args()

    plain = text_blocks.load_stream()
    size = len(plain)
    starts = sorted({int(l.split("\t")[0], 16)
                     for l in TSV.read_text(encoding="utf-8").splitlines()[1:]
                     if len(l.split("\t")) >= 3})
    print(f"{len(starts)} known run starts\n")

    encodings = {
        "absolute": (set(starts), size),
        "minus script start": ({s - SCRIPT_START for s in starts}, size),
        "minus font start": ({s - 0x80 for s in starts}, size),
        "halved": ({s // 2 for s in starts}, size),
        "index 0..n": (set(range(len(starts))), len(starts) * 2),
    }

    archive = ARCHIVE.read_bytes()
    files = [("BOOT.BIN", BOOT.read_bytes()),
             ("0000 stream0", lzss.decompress(archive, 0)[0]),
             ("stream1", plain)]
    for path in sorted(ARCHIVE.parent.iterdir()):
        if path.is_file() and path.name != "0000" and path.stat().st_size < 45_000_000:
            files.append((f"USRDIR/{path.name}", path.read_bytes()))

    print(f"{'file':22s} {'encoding':20s} {'endian':7s} {'hits':>7s} {'vs chance':>10s}")
    found = []
    for name, data in files:
        if len(data) < 8:
            continue
        for big in (False, True):
            values = u32(data, big)
            for label, (wanted, span) in encodings.items():
                hits, ratio = score(values, wanted, span)
                if ratio >= args.min_ratio and hits >= 40:
                    found.append((ratio, name, label, big, hits))
                    print(f"{name:22s} {label:20s} {'BE' if big else 'LE':7s} "
                          f"{hits:7d} {ratio:9.1f}x   <==")
    if not found:
        print("\nnothing above the threshold in any file, encoding or endianness.")
        print("The dialogue is not located through a stored table of offsets.")
    else:
        for ratio, name, label, big, hits in sorted(found, reverse=True)[:5]:
            print(f"\nstrongest: {name} / {label} / {'BE' if big else 'LE'}: "
                  f"{hits} hits at {ratio:.1f}x")


if __name__ == "__main__":
    main()

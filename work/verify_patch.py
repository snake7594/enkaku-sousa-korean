"""Read the finished ISO back the way the console would, and confirm the Korean is in it.

Every check so far ran on intermediate files.  This one starts from the ISO, finds the
archive through its directory record, decompresses stream 1 out of it, and decodes text at
offsets taken from the translation -- so it exercises the whole chain rather than any
single step's own bookkeeping.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import iso9660
import lzss
from decode_script import kanji_index

ISO = Path(r"D:\psp\원격수사\build\Enkaku_Korean.iso")
STREAM1 = 0x27E000


def decode(plain: bytes, start: int, glyph: dict, limit: int = 90) -> str:
    out, at = [], start
    while at < len(plain) and len(out) < limit:
        b = plain[at]
        if 0x88 <= b <= 0x8D and at + 1 < len(plain):
            out.append(glyph.get(kanji_index(b, plain[at + 1]), "?"))
            at += 2
        elif b == 0x11:
            out.append("\n")
            at += 1
        elif b == 0x81 and at + 1 < len(plain):
            out.append({0x40: " ", 0x63: "…", 0x75: "「", 0x76: "」",
                        0x48: "?", 0x49: "!"}.get(plain[at + 1], "·"))
            at += 2
        else:
            break
    return "".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iso", type=Path, default=ISO)
    parser.add_argument("--slots", type=Path,
                        default=Path(r"D:\psp\원격수사\build\korean_slots_full_clean.json"))
    parser.add_argument("--tsv", type=Path,
                        default=Path(r"D:\psp\원격수사\build\translation_ko_clean.tsv"))
    parser.add_argument("--samples", type=int, default=6)
    args = parser.parse_args()

    iso = args.iso.read_bytes()
    record = iso9660.find_record(iso, "/PSP_GAME/USRDIR/0000")
    archive = iso[record.extent * 2048:record.extent * 2048 + record.size]
    print(f"{args.iso.name}: {len(iso)} bytes")
    print(f"   /PSP_GAME/USRDIR/0000 at LBA {record.extent}, {record.size} bytes")

    plain, packed = lzss.decompress(archive, STREAM1)
    print(f"   stream1 packed {packed} -> plain {len(plain)} bytes")

    slots = json.loads(args.slots.read_text(encoding="utf-8"))["slots"]
    glyph = {int(i): ch for ch, i in slots.items()}
    print(f"   {len(glyph)} glyphs in the map")

    rows = [l.split("\t") for l in args.tsv.read_text(encoding="utf-8").splitlines()[1:]]
    rows = [r for r in rows if len(r) >= 3]
    # the offsets in the translation are the *original* ones and everything after the first
    # expansion has moved, so looking there finds nothing.  Search for the encoded bytes
    # instead: it verifies the text reached the ISO without assuming where it landed.
    import encode_korean
    index = {ch: int(i) for ch, i in slots.items()}
    step = max(1, len(rows) // args.samples)
    found = 0
    print("\nsamples located in the patched stream:")
    for row in rows[::step][:args.samples]:
        want = row[2].replace("\\n", "\n")
        encoded = encode_korean.encode_text(want, index)
        at = plain.find(encoded) if encoded else -1
        if at >= 0:
            found += 1
        print(f"   {row[0]} -> {'0x%06x' % at if at >= 0 else 'NOT FOUND':>10s}  "
              f"{decode(plain, at, glyph)[:52]!r}" if at >= 0
              else f"   {row[0]} -> NOT FOUND  {want[:40]!r}")

    every = sum(1 for r in rows
                if (e := encode_korean.encode_text(r[2].replace('\\n', '\n'), index))
                and plain.find(e) >= 0)
    print(f"\n{found}/{args.samples} samples found; "
          f"{every}/{len(rows)} of all translated lines are present in the ISO")


if __name__ == "__main__":
    main()

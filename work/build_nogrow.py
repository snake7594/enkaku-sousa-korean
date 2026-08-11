"""Build a patch that moves nothing: Korean text only where it already fits.

The control ISO runs and the original runs, so the compressor, the archive rebuild and the
emulator are all cleared -- what breaks the game is the expansion or the reference
remapping.  Those two are worth separating from the font and the encoding before chasing
either of them.

So this replaces a line only when its Korean encoding fits inside the Japanese span, pads
the remainder with ideographic spaces, and leaves everything else as Japanese.  No offset
changes, so no reference is touched and the 26,537 rewrites that are the prime suspect do
not happen at all.  If this runs, the font, the glyph map and the encoder are sound and the
fault is squarely in the reflow.  If it does not, the problem is further upstream than the
reflow and the whole reference model needs re-examining rather than adjusting.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import encode_korean

PAD = bytes([0x81, 0x40])          # ideographic space, already used by the encoder


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path,
                        default=Path(r"D:\psp\원격수사\build\stream1_ko_font_clean.bin"))
    parser.add_argument("--tsv", type=Path,
                        default=Path(r"D:\psp\원격수사\build\translation_ko_clean.tsv"))
    parser.add_argument("--slots", type=Path,
                        default=Path(r"D:\psp\원격수사\build\korean_slots_full_clean.json"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    plain = bytearray(args.base.read_bytes())
    slots = {c: int(i) for c, i in
             json.loads(args.slots.read_text(encoding="utf-8"))["slots"].items()}

    fitted = skipped = padded = 0
    for line in args.tsv.read_text(encoding="utf-8").splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        start = int(parts[0], 16)
        end = encode_korean.run_end(plain, start)
        data = encode_korean.encode_text(parts[2].replace("\\n", "\n"), slots)
        if data is None:
            skipped += 1
            continue
        room = end - start
        if len(data) > room:
            skipped += 1
            continue
        gap = room - len(data)
        if gap % 2:                       # cannot pad an odd byte with a two-byte space
            skipped += 1
            continue
        if gap:
            data = data + PAD * (gap // 2)
            padded += 1
        plain[start:end] = data
        fitted += 1

    print(f"{fitted} lines replaced in place ({padded} padded), {skipped} left as Japanese")
    print(f"   stream {len(plain)} bytes -- unchanged, so no reference moves")
    args.out.write_bytes(bytes(plain))
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

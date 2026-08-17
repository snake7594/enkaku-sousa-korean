"""Read the dialogue back out of a built ISO and check it against the translation.

This is the check that was missing.  v3.3 changed which stream the build starts from -- to the
one whose font region matches what was released -- but kept the old slot map, and a slot map
belongs to a font.  Every line still drew, in real Hangul, formed correctly, and every one was
the wrong character.  Nothing in the build objected: markers matched, references resolved, the
archive kept its size.

So the build's own verification is not enough.  What settles it is decoding the shipped bytes
through the same map the font uses and seeing the sentence come back.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import encode_korean
import iso9660
import lzss
import translation_text

ROOT = Path(r"D:\psp\원격수사")
STREAM1 = 0x27E000


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iso", type=Path, default=ROOT / "Enkaku_Korean_v3.5.iso")
    parser.add_argument("--tsv", type=Path,
                        default=ROOT / "build" / "translation_ko_v7_final.tsv")
    parser.add_argument("--slots", type=Path,
                        default=ROOT / "build" / "korean_slots_retranslated_v2.json")
    parser.add_argument("--rows", type=int, default=40)
    args = parser.parse_args()

    record = iso9660.find_record(args.iso.read_bytes(), "/PSP_GAME/USRDIR/0000")
    stream = lzss.decompress(iso9660.read_file(args.iso, record), STREAM1)[0]
    slots = json.loads(args.slots.read_text(encoding="utf-8"))["slots"]
    codes = {c: int(i) for c, i in slots.items()}
    reverse = {int(v): k for k, v in slots.items()}

    _, rows = translation_text.parse_loose_tsv(args.tsv)
    wanted = [r for r in rows if len(r) >= 3][: args.rows]

    good = bad = 0
    for row in wanted:
        # Encode the line the way the build does and look for those exact bytes.  Picking a few
        # characters and encoding them by hand does not work: the line also carries spaces and
        # punctuation that live outside the slot table, so a hand-made run is never contiguous
        # in the stream.  Later text moves as the script grows, so the check is on the bytes,
        # not on where they sit.
        encoded = encode_korean.encode_text(row[2].replace(r"\n", "\n"), codes)
        if not encoded or len(encoded) < 8:
            continue
        if encoded in stream:
            good += 1
        else:
            bad += 1
            if bad <= 5:
                print(f"   not found: {row[0]}  {row[2][:40]}")
    print(f"{good} of {good + bad} sampled rows found in the stream, encoded as written")

    at = stream.find(b"\x89\x7d")
    reading = []
    for i in range(0x2AC87, 0x2AC87 + 24, 2):
        code = (stream[i] << 8) | stream[i + 1]
        reading.append(reverse.get(code - 0x8800, "·") if code >= 0x8800 else "·")
    print(f"first row reads: {''.join(reading)}")
    raise SystemExit(0 if bad == 0 else 1)


if __name__ == "__main__":
    main()

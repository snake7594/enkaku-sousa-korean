"""Measure whether the Korean stream still fits the archive, before rearranging anything.

Everything downstream hangs on one number.  Stream 1 is packed into 605,757 bytes and the
trailing blob begins immediately after, so there is exactly zero slack; if the Korean
stream packs under that, the archive keeps its size, the ISO keeps its layout, and the
relocation problem does not exist.  If it does not fit, the overflow says how much room has
to be found.

The estimate that suggested trouble (~670 KB) assumed Korean compresses like Japanese, and
it will not: Hangul is a two-byte code drawn from a small syllable set with heavily repeated
particles, which is exactly what an LZ window is good at.  Guessing either way is pointless
when the compressor can be run.

One thing this exposes: the translation's offsets start at 0x0002AC87, well before the
first `07 1C` marker at 0x038B78, so text also lives outside marked blocks.  Reflow keyed
on blocks would silently skip those, so spans come from the translation itself.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import encode_korean
import lz11_compress
import text_blocks

BUDGET = 0x93C3D          # packed size of the original stream 1; the blob starts right after


def load_spans(plain: bytes, tsv: Path, slots: dict) -> tuple[list, dict]:
    spans, stats = [], {"rows": 0, "encoded": 0, "failed": 0}
    for line in tsv.read_text(encoding="utf-8").splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        stats["rows"] += 1
        start = int(parts[0], 16)
        text = parts[2].replace("\\n", "\n")
        encoded = encode_korean.encode_text(text, slots)
        if encoded is None:
            stats["failed"] += 1
            continue
        stats["encoded"] += 1
        spans.append((start, encode_korean.run_end(plain, start), encoded))
    spans.sort()
    return spans, stats


def splice(plain: bytes, spans: list) -> bytes:
    out, cursor, dropped = bytearray(), 0, 0
    for start, end, data in spans:
        if start < cursor:                 # overlapping runs would corrupt the stream
            dropped += 1
            continue
        out += plain[cursor:start]
        out += data
        cursor = end
    out += plain[cursor:]
    if dropped:
        print(f"   {dropped} overlapping spans skipped")
    return bytes(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tsv", type=Path,
                        default=Path(r"D:\psp\원격수사\build\translation_ko.tsv"))
    parser.add_argument("--slots", type=Path,
                        default=Path(r"D:\psp\원격수사\build\korean_slots.json"))
    parser.add_argument("--chain", type=int, default=64)
    parser.add_argument("--base", type=Path, default=None,
                        help="stream to splice into; use the one carrying the Korean font")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    # measuring against the Japanese font understates the case: the font is 175,104 of the
    # stream's bytes and Hangul at 16x16 is far more regular than kanji, so the glyph table
    # itself packs differently once it holds the replacement.
    plain = args.base.read_bytes() if args.base else text_blocks.load_stream()
    # the map file wraps the assignment in metadata; the encoder wants the inner dict.
    # Passing the whole file makes every lookup miss and reads as an empty font.
    raw = json.loads(args.slots.read_text(encoding="utf-8"))
    slots = {ch: int(i) for ch, i in raw["slots"].items()}
    print(f"{len(slots)} glyph slots assigned")
    spans, stats = load_spans(plain, args.tsv, slots)
    print(f"{stats['rows']} translation rows: {stats['encoded']} encoded, "
          f"{stats['failed']} could not be encoded")

    old_bytes = sum(e - s for s, e, _ in spans)
    new_bytes = sum(len(d) for _, _, d in spans)
    print(f"   text {old_bytes} -> {new_bytes} bytes "
          f"({100.0 * new_bytes / old_bytes:.1f}% of the Japanese)")

    grown = splice(plain, spans)
    print(f"   stream {len(plain)} -> {len(grown)} bytes (+{len(grown) - len(plain)})")

    print("\ncompressing ...")
    packed = lz11_compress.compress(grown, max_chain=args.chain)
    print(f"   packed {len(packed)} bytes; budget {BUDGET} "
          f"({BUDGET - len(packed):+d})")
    if len(packed) <= BUDGET:
        print("   it fits -- the archive keeps its size and the ISO needs no relocation")
    else:
        over = len(packed) - BUDGET
        print(f"   {over} bytes over ({100.0 * over / BUDGET:.1f}%); the archive has to grow")

    if args.out:
        args.out.write_bytes(grown)
        print(f"-> {args.out}")


if __name__ == "__main__":
    main()

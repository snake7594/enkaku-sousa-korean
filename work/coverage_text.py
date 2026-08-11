"""Check how much of the script's text actually falls inside the detected spans.

Span detection keys off the 07 1C / 12 10 markers.  If some text uses different
markers it would be silently missing from the export, so this counts every kanji and
kana code in the whole stream and compares against what the spans capture.
"""

from __future__ import annotations

import argparse
from collections import Counter

from decode_script import (HIRA, HIRA_BASE, KANJI_HI, KANJI_LO, LEAD_HI,
                           LEAD_LO, STREAM, text_spans)

TEXT_START = 0x2AC80   # right after the glyph table


def scan_codes(data: bytes, start: int, end: int) -> tuple[Counter, set[int]]:
    """Count kanji/kana codes, tokenising the same way the decoder does."""
    counts = Counter()
    positions = set()
    i = start
    while i < end:
        b = data[i]
        if LEAD_LO <= b <= LEAD_HI and i + 1 < end:
            if KANJI_LO <= b <= KANJI_HI:
                counts["kanji"] += 1
                positions.add(i)
            else:
                counts["punct"] += 1
            i += 2
            continue
        if HIRA_BASE <= b < HIRA_BASE + len(HIRA):
            counts["hira"] += 1
        elif 0xA1 <= b <= 0xDF:
            counts["kata"] += 1
        i += 1
    return counts, positions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=lambda v: int(v, 0), default=TEXT_START)
    args = parser.parse_args()

    data = STREAM.read_bytes()
    whole, whole_pos = scan_codes(data, args.start, len(data))
    print(f"whole stream 0x{args.start:x}-0x{len(data):x}: {dict(whole)}")

    spans = text_spans(data)
    covered = 0
    span_bytes = 0
    inside = set()
    for offset, span in spans:
        span_bytes += len(span)
        _, pos = scan_codes(data, offset, offset + len(span))
        inside |= pos
    covered = len(inside & whole_pos)
    print(f"{len(spans)} spans, {span_bytes} bytes")
    print(f"kanji codes inside spans: {covered}/{len(whole_pos)} "
          f"({covered * 100 / max(1, len(whole_pos)):.1f}%)")

    missed = sorted(whole_pos - inside)
    print(f"kanji codes outside any span: {len(missed)}")
    if missed:
        print("first few outside positions:")
        for pos in missed[:12]:
            lo = max(args.start, pos - 12)
            chunk = data[lo : pos + 20]
            print(f"   0x{pos:08x}  " + " ".join(f"{b:02x}" for b in chunk))


if __name__ == "__main__":
    main()

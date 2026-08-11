"""Separate slots the charmap collapsed onto one character, then apply what is safe.

The 恋 conflict turned out not to be a one-off.  恋 sits in slots 425 and 428, but 真 occupies
four slots, and 新, 関, 裏, 能, 機, 来 and 何 three each -- the charmap has been assigning the
same character to several distinct glyphs, so a whole family of characters is being read as
whichever one happened to win.  That is the mechanism behind every misreading the quality
review kept meeting, and it is why fixing dialogue line by line was so slow: each wrong
character is wrong everywhere it appears.

Applying a correction therefore needs to know *which* slot to change.  Where the wrong
character occupies a single slot the answer is unambiguous and the fix goes in.  Where it
occupies several, each slot is used in different words, and this separates them by looking
at what actually follows each one in the stream.

charmap_final.json is never modified; the result is written alongside it.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import lzss
from decode_script import kanji_code

ROOT = Path(r"D:\psp\원격수사")
CHARMAP = ROOT / "font_extract" / "charmap_final.json"
ADDITIONAL = ROOT / "font_extract" / "translation_quality_additional_kanji.json"
STREAM = ROOT / "iso_extract" / "PSP_GAME" / "USRDIR" / "0000"
STREAM1 = 0x27E000
OUT_MAP = ROOT / "font_extract" / "charmap_quality_corrected.json"
OUT_REPORT = ROOT / "build" / "charmap_duplicate_report.json"


def contexts(plain: bytes, slot: int, charmap: list, limit: int = 6) -> list[str]:
    """A few short windows of decoded text around each use of this slot."""
    code = kanji_code(slot)
    out, at = [], 0
    while len(out) < limit:
        at = plain.find(code, at)
        if at < 0:
            break
        window = []
        for i in range(max(0, at - 6), min(len(plain) - 1, at + 8), 2):
            b = plain[i]
            if 0x88 <= b <= 0x8D:
                idx = (b - 0x88) * 253 + plain[i + 1]
                if 0 <= idx < len(charmap):
                    window.append(charmap[idx].get("char") or "?")
            else:
                window.append("·")
        out.append("".join(window))
        at += 2
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    args = parser.parse_args()

    charmap = json.loads(CHARMAP.read_text(encoding="utf-8"))
    entries = json.loads(ADDITIONAL.read_text(encoding="utf-8"))["entries"]
    confirmed = {e["glyph_or_byte"]: e["candidate_character"]
                 for e in entries if e["status"] == "confirmed"}
    plain = lzss.decompress(STREAM.read_bytes(), STREAM1)[0]

    slots_of = defaultdict(list)
    for i, e in enumerate(charmap):
        ch = e.get("char")
        if ch:
            slots_of[ch].append(i)

    duplicates = {c: s for c, s in slots_of.items() if len(s) > 1}
    print(f"{len(duplicates)} characters occupy more than one slot "
          f"({sum(len(s) for s in duplicates.values())} slots in all)")

    applied, ambiguous = [], []
    corrected = json.loads(json.dumps(charmap))
    for wrong, right in confirmed.items():
        slots = slots_of.get(wrong, [])
        if len(slots) == 1:
            slot = slots[0]
            corrected[slot] = {**corrected[slot], "char": right,
                               "source": "translation_quality_review",
                               "confidence": "high",
                               "previous_char": wrong}
            applied.append({"slot": slot, "from": wrong, "to": right,
                            "uses": charmap[slot].get("uses", 0)})
        else:
            ambiguous.append({"character": wrong, "proposed": right, "slots": slots,
                              "contexts": {str(s): contexts(plain, s, charmap)
                                           for s in slots}})

    # the conflicting pair, separated by what each slot is used in
    conflict = {"character": "恋", "slots": slots_of.get("恋", []),
                "candidates": {"受": "恋付 -> 受付", "時": "当恋 -> 当時"},
                "contexts": {str(s): contexts(plain, s, charmap)
                             for s in slots_of.get("恋", [])}}

    OUT_MAP.write_text(json.dumps(corrected, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    OUT_REPORT.write_text(json.dumps({
        "schema": "enkaku_charmap_duplicate_report_v1",
        "duplicate_characters": {c: s for c, s in sorted(
            duplicates.items(), key=lambda kv: -len(kv[1]))[:40]},
        "duplicate_count": len(duplicates),
        "applied": applied,
        "ambiguous": ambiguous,
        "conflict": conflict,
        "emulator_launched": False,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n{len(applied)} corrections applied to a single unambiguous slot:")
    for a in applied:
        print(f"   slot {a['slot']:5d}  {a['from']} -> {a['to']}   ({a['uses']} uses)")
    print(f"\n{len(ambiguous)} left ambiguous because the character owns several slots:")
    for a in ambiguous:
        print(f"   {a['character']} -> {a['proposed']}  slots {a['slots']}")
    print(f"\n恋 slots {conflict['slots']}")
    for slot, ctx in conflict["contexts"].items():
        print(f"   slot {slot}: {ctx[:4]}")
    print(f"\n-> {OUT_MAP}\n-> {OUT_REPORT}")


if __name__ == "__main__":
    main()

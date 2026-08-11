"""Decide 175 disputed glyph slots using the name plates as ground truth.

Two readings exist for these slots.  charmap_quality_corrected.json holds what the glyph
looked like when it was rendered and read by eye; charmap_additional_confirmed.json holds an
earlier context-guessed confirmation, and because rebuild_ja_corrected.py applies the ledger
last, the guess wins wherever the two disagree.

Argument from plausibility is what produced the mess, so this does not argue.  The character
name plates are pictures of text -- no glyph table stands between the artist and the player --
so the kanji on them are simply true.  For each plate name, count how many times each map
renders that exact name out of the raw token stream.  A map that spells 白川真二 where the
plate says 白川真二 is reading those slots correctly; a map that spells 白川真了 is not.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")
FONT = ROOT / "font_extract"
TOK = re.compile(r"\[(\d+)\]|(.)")

# The names as they are painted on the plates, from build/nameplate_report.json.
PLATES = ["水無月葵", "神崎茜", "近藤克美", "吉本清香", "水谷朝露", "三浦正信",
          "新城法子", "白川安代", "七芝伊月", "吉本ユミ", "白川悟", "斉藤佳代",
          "斉藤志朗", "白川一朗", "白川真二", "白川美佐恵"]


def build_maps():
    quality = json.loads((FONT / "charmap_quality_corrected.json").read_text(encoding="utf-8"))
    glyph = {int(e["index"]): e["char"] for e in quality}
    ledger = dict(glyph)
    extra = json.loads((FONT / "charmap_additional_confirmed.json").read_text(encoding="utf-8"))
    for item in extra.get("character_confirmations", []):
        ids, confirmed = item.get("glyph_indices", []), item.get("confirmed", "")
        if len(ids) == len(confirmed):
            ledger.update({int(i): c for i, c in zip(ids, confirmed)})
    disputed = {s for s, c in glyph.items()
                if ledger.get(s) != c
                and next(e for e in quality if int(e["index"]) == s).get("source")
                == "glyph_image_reading"}
    return glyph, ledger, disputed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "charmap_adjudication.json")
    args = parser.parse_args()

    glyph, ledger, disputed = build_maps()
    _, raw = translation_text.parse_loose_tsv(FONT / "script_full_raw.tsv")
    seqs = [[int(m.group(1)) if m.group(1) else m.group(2) for m in TOK.finditer(r[-1])]
            for r in raw if len(r) >= 2]

    def render(seq, mapping):
        return "".join(mapping.get(t, "\ufffd") if isinstance(t, int) else t for t in seq)

    glyph_text = [render(s, glyph) for s in seqs]
    ledger_text = [render(s, ledger) for s in seqs]

    rows, slots_touched = [], Counter()
    for name in PLATES:
        g = sum(t.count(name) for t in glyph_text)
        l = sum(t.count(name) for t in ledger_text)
        # which disputed slots take part in spelling this name under the glyph map
        used = set()
        for seq, text in zip(seqs, glyph_text):
            if name not in text:
                continue
            for i, t in enumerate(seq):
                if isinstance(t, int) and t in disputed and glyph[t] in name:
                    used.add(t)
        rows.append({"name": name, "glyph_map": g, "ledger_map": l,
                     "disputed_slots": sorted(used)})
        if g > l:
            slots_touched.update(used)

    won = sum(1 for r in rows if r["glyph_map"] > r["ledger_map"])
    lost = sum(1 for r in rows if r["ledger_map"] > r["glyph_map"])

    args.out.write_text(json.dumps({
        "schema": "enkaku_charmap_adjudication_v1",
        "disputed_slots": len(disputed),
        "plates_glyph_map_wins": won, "plates_ledger_map_wins": lost,
        "disputed_slots_vindicated_by_a_plate": sorted(slots_touched),
        "plates": rows,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(disputed)} disputed slots\n")
    print(f"{'plate name':14s} {'glyph map':>10s} {'ledger map':>11s}   disputed slots")
    for r in rows:
        mark = "  <-" if r["glyph_map"] > r["ledger_map"] else (
            "  !!" if r["ledger_map"] > r["glyph_map"] else "")
        print(f"{r['name']:14s} {r['glyph_map']:10d} {r['ledger_map']:11d}   "
              f"{r['disputed_slots']}{mark}")
    print(f"\nplates spelled correctly only by the glyph map: {won}")
    print(f"plates spelled correctly only by the ledger:     {lost}")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

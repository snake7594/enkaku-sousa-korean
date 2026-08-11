"""Show the revised glyph slots in their real contexts, under both readings.

script_full_ja.tsv is generated from charmap_final + charmap_additional_confirmed.  The later
glyph-image pass wrote charmap_quality_corrected.json and nothing regenerates from it, so 128
slots that were read off the rendered glyph never reached the Japanese the translation was
built from.  斉藤佳代 was one of them, and the name plate proved that one right.

Whether the other 127 are right is a separate question, and pairs are no test: 可能, 計算 and
連携 all looked like the old map was correct, but those slots never occur next to each other,
so the words were never in the script to begin with.  The honest test is to print each slot
where it actually appears and read the surrounding Japanese.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")
FONT = ROOT / "font_extract"
TOK = re.compile(r"\[(\d+)\]|(.)")


def render(seq, mapping):
    return "".join(mapping.get(t, f"□{t}□") if isinstance(t, int) else t for t in seq)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument("--width", type=int, default=9)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "charmap_conflict.json")
    args = parser.parse_args()

    entries = json.loads((FONT / "charmap_final.json").read_text(encoding="utf-8"))
    old = {int(e["index"]): e["char"] for e in entries}
    extra = json.loads((FONT / "charmap_additional_confirmed.json").read_text(encoding="utf-8"))
    for item in extra.get("character_confirmations", []):
        ids, confirmed = item.get("glyph_indices", []), item.get("confirmed", "")
        if len(ids) == len(confirmed):
            old.update(zip(ids, confirmed))

    quality = json.loads((FONT / "charmap_quality_corrected.json").read_text(encoding="utf-8"))
    new = dict(old)
    revised = {}
    for e in quality:
        if e.get("previous_char") and e["char"] != old.get(e["index"]):
            new[e["index"]] = e["char"]
            revised[e["index"]] = (old.get(e["index"], "?"), e["char"], e.get("uses", 0),
                                   e.get("confidence", ""))

    _, raw = translation_text.parse_loose_tsv(FONT / "script_full_raw.tsv")
    seqs = [(r[0], [int(m.group(1)) if m.group(1) else m.group(2)
                    for m in TOK.finditer(r[-1])]) for r in raw if len(r) >= 2]

    report = []
    for slot, (o, n, uses, conf) in sorted(revised.items(), key=lambda kv: -kv[1][2]):
        samples = []
        for key, seq in seqs:
            for i, t in enumerate(seq):
                if t == slot:
                    lo, hi = max(0, i - args.width), i + args.width + 1
                    samples.append({"index": key,
                                    "old": render(seq[lo:hi], old),
                                    "new": render(seq[lo:hi], new)})
                    break
            if len(samples) >= 3:
                break
        report.append({"slot": slot, "old": o, "new": n, "uses": uses,
                       "confidence": conf, "samples": samples})

    args.out.write_text(json.dumps({"schema": "enkaku_charmap_conflict_v1",
                                    "revised_slots": len(revised), "slots": report},
                                   ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(revised)} slots read differently by the glyph-image pass\n")
    for row in report[: args.top]:
        print(f"slot {row['slot']:4d}  {row['old']} -> {row['new']}   "
              f"{row['uses']} uses, {row['confidence']}")
        for s in row["samples"][:2]:
            print(f"     old  {s['old']}")
            print(f"     new  {s['new']}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

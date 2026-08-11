"""Rebuild the Japanese source without the stale ledger overriding the glyph readings.

rebuild_ja_corrected.py starts from charmap_quality_corrected.json -- the pass that rendered
each glyph and read it -- and then applies charmap_additional_confirmed.json's
character_confirmations on top.  The ledger is the older, context-guessed pass, so for 175
slots a guess overwrites a reading.  That is how 斉藤佳代 came out 勝代 and 白川真二 came out
真了.

The name plates settle it without argument.  They are pictures of text, so their kanji are
ground truth, and where a disputed slot spells a plate name the glyph map spells the plate's
own name 4 times out of 4 -- 白川真二 61x, 斉藤佳代 29x, 水無月葵 7x, 吉本清香 2x -- while the
ledger spells nothing.  Not one plate goes the other way.

So character_confirmations are skipped exactly where they contradict a glyph_image_reading,
and kept everywhere else.  Phrase and scoped confirmations are untouched: those name a whole
word rather than a lone slot, and they are what recovered 播磨 and 宮上銀座.

Written to a new file.  The old one stays until the translation has caught up with it.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
FONT = ROOT / "font_extract"
TOKEN = re.compile(r"\[(\d+)\]")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path, default=FONT / "script_full_ja_corrected.tsv")
    parser.add_argument("--out", type=Path, default=FONT / "script_full_ja_v4.tsv")
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "ja_v4_report.json")
    args = parser.parse_args()

    quality = json.loads((FONT / "charmap_quality_corrected.json").read_text(encoding="utf-8"))
    mapping = {int(e["index"]): e["char"] for e in quality}
    by_glyph = {int(e["index"]) for e in quality if e.get("source") == "glyph_image_reading"}

    extra = json.loads((FONT / "charmap_additional_confirmed.json").read_text(encoding="utf-8"))
    applied, skipped = 0, []
    for item in extra.get("character_confirmations", []):
        ids, confirmed = item.get("glyph_indices", []), item.get("confirmed", "")
        if len(ids) != len(confirmed):
            continue
        for index, char in zip(ids, confirmed):
            slot = int(index)
            if slot in by_glyph and mapping.get(slot) != char:
                skipped.append({"slot": slot, "glyph_read": mapping.get(slot),
                                "ledger_said": char})
                continue
            mapping[slot] = char
            applied += 1

    phrase = []
    for item in extra.get("phrase_confirmations", []):
        ids = item.get("glyph_indices", item.get("raw_indices", []))
        confirmed = item.get("confirmed", "")
        if len(ids) == len(confirmed):
            phrase.append(("".join(mapping.get(int(i), f"□{i}□") for i in ids), confirmed))

    scoped = []
    for item in extra.get("scoped_phrase_confirmations", []):
        rows = {int(x) for x in item.get("raw_row_indices", [])}
        pattern = item.get("raw_pattern", "") or "".join(
            f"[{int(i)}]" for i in item.get("glyph_indices", []))
        confirmed = item.get("confirmed", "")
        if rows and pattern and confirmed:
            scoped.append((rows, pattern, confirmed))
    scoped.sort(key=lambda x: len(x[1]), reverse=True)

    with args.previous.open(encoding="utf-8-sig", newline="") as fh:
        before = {r["offset"]: r["text"] for r in csv.DictReader(fh, delimiter="\t")}
    with (FONT / "script_full_raw.tsv").open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))

    changed, unresolved = [], 0
    with args.out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["offset", "lines", "text"],
                                delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for order, row in enumerate(rows):
            raw_text = row["text"]
            for row_indices, pattern, confirmed in scoped:
                if order in row_indices and pattern in raw_text:
                    raw_text = raw_text.replace(pattern, confirmed)
            text = TOKEN.sub(lambda m: mapping.get(int(m.group(1)), f"□{m.group(1)}□"), raw_text)
            for observed, confirmed in phrase:
                if observed and observed in text:
                    text = text.replace(observed, confirmed)
            unresolved += text.count("□") // 2
            old = before.get(row["offset"])
            if old is not None and old != text:
                changed.append({"offset": row["offset"], "before": old, "after": text})
            writer.writerow({"offset": row["offset"], "lines": row["lines"], "text": text})

    args.report.write_text(json.dumps({
        "schema": "enkaku_ja_v4_v1", "rows": len(rows), "changed_rows": len(changed),
        "confirmations_applied": applied, "confirmations_skipped": len(skipped),
        "unresolved_glyphs": unresolved,
        "skipped": sorted(skipped, key=lambda s: s["slot"]), "changes": changed,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{applied} ledger confirmations applied, {len(skipped)} skipped as contradicted")
    print(f"{len(changed)} of {len(rows)} rows change, {unresolved} glyphs still unresolved")
    for c in changed[:6]:
        print(f"   {c['offset']}\n     - {c['before'][:76]}\n     + {c['after'][:76]}")
    print(f"-> {args.out}\n-> {args.report}")


if __name__ == "__main__":
    main()

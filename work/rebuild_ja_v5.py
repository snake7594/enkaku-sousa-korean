"""Build the Japanese source from readings rather than from guesses.

Three passes wrote the glyph map, and rebuild_ja_corrected.py applied them in the wrong
order: it starts from charmap_quality_corrected.json, which holds what each glyph looked like
when it was rendered and read, and then lets charmap_additional_confirmed.json overwrite it,
which is the older pass that guessed from context.  So a guess beat a reading on 175 slots.

The plates decide it, because a plate is a picture and a picture has no glyph table in it.
Counting the plate names in the script, the readings spell them 4 times out of 4 -- 白川真二
61x, 斉藤佳代 29x, 水無月葵 7x, 吉本清香 2x -- and the guesses spell none.

charmap_glyph_audit.json is then a further 54 slots that no pass had ever looked at, read the
same way.  That is where 従業員, 定休日, 樋口, 音源, 白川一朗 and 水無月幸司 come back.

Order here is: read the glyph, then let a confirmation override only if it is not arguing
with a reading, then apply phrase confirmations, which name a whole word and outrank
everything.  Writes a new file and leaves the old one alone.
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
    parser.add_argument("--audit", type=Path, default=FONT / "charmap_glyph_audit.json")
    parser.add_argument("--out", type=Path, default=FONT / "script_full_ja_v5.tsv")
    parser.add_argument("--charmap-out", type=Path, default=FONT / "charmap_v5.json")
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "ja_v5_report.json")
    args = parser.parse_args()

    quality = json.loads((FONT / "charmap_quality_corrected.json").read_text(encoding="utf-8"))
    mapping = {int(e["index"]): e["char"] for e in quality}
    read_by_eye = {int(e["index"]) for e in quality if e.get("source") == "glyph_image_reading"}

    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    for entry in audit["readings"]:
        mapping[int(entry["slot"])] = entry["char"]
        read_by_eye.add(int(entry["slot"]))

    extra = json.loads((FONT / "charmap_additional_confirmed.json").read_text(encoding="utf-8"))
    applied, skipped = 0, []
    for item in extra.get("character_confirmations", []):
        ids, confirmed = item.get("glyph_indices", []), item.get("confirmed", "")
        if len(ids) != len(confirmed):
            continue
        for index, char in zip(ids, confirmed):
            slot = int(index)
            if slot in read_by_eye and mapping.get(slot) != char:
                skipped.append({"slot": slot, "read": mapping.get(slot), "guessed": char})
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

    args.charmap_out.write_text(json.dumps(
        {"schema": "enkaku_charmap_v5", "note": "readings first, guesses only where they do "
         "not contradict a reading, phrase confirmations last",
         "map": {str(k): v for k, v in sorted(mapping.items())}},
        ensure_ascii=False, indent=1), encoding="utf-8")
    args.report.write_text(json.dumps({
        "schema": "enkaku_ja_v5_v1", "rows": len(rows), "changed_rows": len(changed),
        "audit_readings": len(audit["readings"]),
        "confirmations_applied": applied, "confirmations_skipped": len(skipped),
        "unresolved_glyphs": unresolved,
        "skipped": sorted(skipped, key=lambda s: s["slot"]), "changes": changed,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(audit['readings'])} audited readings + the glyph pass; "
          f"{applied} guesses kept, {len(skipped)} dropped as contradicted")
    print(f"{len(changed)} of {len(rows)} rows change, {unresolved} glyphs still unresolved")
    print(f"-> {args.out}\n-> {args.charmap_out}\n-> {args.report}")


if __name__ == "__main__":
    main()

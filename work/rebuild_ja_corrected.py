"""Regenerate the applied Japanese TSV using the separate confirmation ledger."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "font_extract"
RAW = FONT / "script_full_raw.tsv"
OUT = FONT / "script_full_ja_corrected.tsv"
TOKEN = re.compile(r"\[(\d+)\]")


def main() -> None:
    entries = json.loads((FONT / "charmap_quality_corrected.json").read_text(encoding="utf-8"))
    mapping = {int(x["index"]): x["char"] for x in entries}
    extra = json.loads((FONT / "charmap_additional_confirmed.json").read_text(encoding="utf-8"))
    phrase_replacements: list[tuple[str, str]] = []
    scoped_phrase_replacements: list[tuple[set[int], str, str]] = []
    applied = 0
    for item in extra.get("character_confirmations", []):
        ids = item.get("glyph_indices", [])
        confirmed = item.get("confirmed", "")
        if len(ids) == len(confirmed):
            mapping.update(zip(ids, confirmed))
            applied += len(ids)
    # Phrase confirmations are applied to the exact mapped phrase, not to the
    # global glyph map.  Some code points are reused in unrelated contexts
    # (for example [280] is 川 in 中川理 but 付 in 駆け付ける), so projecting a
    # phrase component globally would corrupt the rest of the script.
    for item in extra.get("phrase_confirmations", []):
        # The original ledger used raw_indices for phrase-level observations;
        # newer records use glyph_indices.  Accept both so confirmed names and
        # fixed terms are actually reflected in script_full_ja.tsv.
        ids = item.get("glyph_indices", item.get("raw_indices", []))
        confirmed = item.get("confirmed", "")
        if len(ids) == len(confirmed):
            observed = "".join(mapping.get(int(index), f"□{index}□") for index in ids)
            phrase_replacements.append((observed, confirmed))

    # Some glyphs are reused by the game's compact text/font tables.  Keep
    # those repairs row-scoped and operate on the raw token sequence before
    # the normal per-glyph substitution.  This prevents a context such as
    # [480]=男 from changing unrelated 人 or speaker-label occurrences.
    for item in extra.get("scoped_phrase_confirmations", []):
        rows = {int(x) for x in item.get("raw_row_indices", [])}
        pattern = item.get("raw_pattern", "")
        ids = item.get("glyph_indices", [])
        if not pattern and ids:
            pattern = "".join(f"[{int(index)}]" for index in ids)
        confirmed = item.get("confirmed", "")
        if rows and pattern and confirmed:
            scoped_phrase_replacements.append((rows, pattern, confirmed))
    # Apply the most specific token sequence first.  For example, a scoped
    # [789]い[480] repair must run before a one-token [480] repair.
    scoped_phrase_replacements.sort(key=lambda x: len(x[1]), reverse=True)

    with RAW.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["offset", "lines", "text"], delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for order, row in enumerate(rows):
            raw_text = row["text"]
            # [279][280] is the recurring 中川 name; [280] is 付 in the
            # remaining ordinary-word contexts (駆け付ける, 付き合い,
            # 付ける, etc.).  This is deliberately local because the same
            # slot is also used by the name's 川.
            raw_text = raw_text.replace("[279][280][192]", "中川理")
            raw_text = raw_text.replace("[279][280]", "中川")
            local_mapping = mapping.copy()
            local_mapping[280] = "付"
            for row_indices, pattern, confirmed in scoped_phrase_replacements:
                if order in row_indices and pattern in raw_text:
                    raw_text = raw_text.replace(pattern, confirmed)
                    applied += 1
            text = TOKEN.sub(lambda m: local_mapping.get(int(m.group(1)), f"□{m.group(1)}□"), raw_text)
            for observed, confirmed in phrase_replacements:
                if observed and observed in text:
                    text = text.replace(observed, confirmed)
                    applied += 1
            writer.writerow({"offset": row["offset"], "lines": row["lines"], "text": text})
    print(f"wrote {OUT} ({len(rows)} rows, {applied} confirmed glyph assignments applied)")


if __name__ == "__main__":
    main()


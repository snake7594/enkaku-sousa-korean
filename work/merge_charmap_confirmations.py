"""Promote the latest context confirmations into the canonical charmap artifacts.

Claude Code's later analysis produced ``charmap_v2.json`` and kept the stronger
context/ruby decisions in ``charmap_additional_confirmed.json``.  Several
downstream tools still expect the canonical ``charmap_final`` pair, so this
generator joins those two sources without altering the exploratory v2 file.

Only indices that belong to the original 0..1367 glyph table are written here;
out-of-range script slots remain documented in the additional-confirmation
ledger and are applied by the script rebuild step.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "font_extract"
SOURCE = FONT / "charmap_v2.json"
CONFIRMATIONS = FONT / "charmap_additional_confirmed.json"
OUT_JSON = FONT / "charmap_final.json"
OUT_TSV = FONT / "charmap_final.tsv"


def main() -> None:
    table = json.loads(SOURCE.read_text(encoding="utf-8"))
    if not isinstance(table, list) or len(table) != 1368:
        raise SystemExit(f"unexpected source charmap size: {len(table) if isinstance(table, list) else type(table).__name__}")

    by_index = {int(item["index"]): dict(item) for item in table}
    if set(by_index) != set(range(1368)):
        raise SystemExit("source charmap does not cover exactly indices 0..1367")

    extra = json.loads(CONFIRMATIONS.read_text(encoding="utf-8"))
    confirmed: dict[int, str] = {}
    for item in extra.get("character_confirmations", []):
        indices = [int(value) for value in item.get("glyph_indices", [])]
        chars = item.get("confirmed", "")
        if len(indices) != len(chars):
            raise SystemExit(f"malformed confirmation record: {item!r}")
        for index, char in zip(indices, chars):
            previous = confirmed.get(index)
            if previous is not None and previous != char:
                raise SystemExit(f"conflicting confirmation for {index}: {previous!r} vs {char!r}")
            confirmed[index] = char

    promoted = 0
    for index, char in confirmed.items():
        if index not in by_index:
            continue
        item = by_index[index]
        if item.get("char") != char:
            promoted += 1
        item["char"] = char
        item["source"] = "additional_context_confirmed"
        item["confidence"] = "high"

    final = [by_index[index] for index in range(1368)]
    OUT_JSON.write_text(json.dumps(final, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    with OUT_TSV.open("w", encoding="utf-8", newline="\n") as fh:
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n")
        writer.writerow(("index", "char", "source", "confidence", "uses", "alts"))
        for item in final:
            writer.writerow((
                item["index"], item["char"], item.get("source", ""),
                item.get("confidence", ""), item.get("uses", 0),
                "".join(item.get("alts", [])),
            ))

    print(f"canonical charmap: {len(final)} glyphs")
    print(f"context confirmations promoted: {promoted}")
    print(f"-> {OUT_JSON}")
    print(f"-> {OUT_TSV}")


if __name__ == "__main__":
    main()

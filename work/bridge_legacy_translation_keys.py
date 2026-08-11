"""Keep old by_japanese_applied translation keys after a charmap refresh."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "font_extract"
TOKEN = re.compile(r"\[(\d+)\]")


def main() -> None:
    charmap = json.loads((FONT / "charmap_final.json").read_text(encoding="utf-8"))
    legacy_map = {int(x["index"]): x["char"] for x in charmap}
    data = json.loads((FONT / "translation_overrides.json").read_text(encoding="utf-8"))
    by_text = data.setdefault("by_japanese_applied", {})
    raw_rows = list(csv.DictReader((FONT / "script_full_raw.tsv").open(encoding="utf-8-sig", newline=""), delimiter="\t"))
    current_rows = list(csv.DictReader((FONT / "script_full_ja.tsv").open(encoding="utf-8-sig", newline=""), delimiter="\t"))
    bridged = 0
    for raw, current in zip(raw_rows, current_rows):
        legacy = TOKEN.sub(lambda m: legacy_map.get(int(m.group(1)), f"□{m.group(1)}□"), raw["text"])
        korean = by_text.get(legacy)
        if korean is not None and current["text"] not in by_text:
            by_text[current["text"]] = korean
            bridged += 1
    data["by_japanese_applied"] = by_text
    data["notes"] = "Model-assisted hand translation overrides; legacy and confirmation-updated Japanese keys are both retained."
    (FONT / "translation_overrides.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"bridged translation keys: {bridged}")
    print(f"by_japanese_applied total: {len(by_text)}")


if __name__ == "__main__":
    main()

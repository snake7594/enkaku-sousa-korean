"""Materialize the Claude-facing full translation ledger by row order.

The project kept 7,841 entries in ``by_order`` and the rest only through a
Japanese-text key.  Text-keyed lookup becomes fragile after a charmap rebuild,
so this pass fills missing row keys from the already translated context while
leaving every existing row-keyed translation untouched.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "font_extract"
OVERRIDES = FONT / "translation_overrides.json"
CONTEXT = FONT / "translation_context_for_claude.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    data = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    context = json.loads(CONTEXT.read_text(encoding="utf-8"))
    by_order = data.setdefault("by_order", {})
    added = 0
    skipped = 0
    for entry in context.get("entries", []):
        order = str(entry["order"])
        translation = entry.get("translation", {})
        korean = translation.get("korean")
        if not korean:
            skipped += 1
            continue
        existing = by_order.get(order)
        if existing and existing.get("korean"):
            continue
        by_order[order] = {
            "korean": korean,
            "notes": "행 순서 키로 materialize한 기존 Claude 번역; 원문·문맥 장부에서 복원.",
        }
        added += 1

    print(f"row-keyed translations: {len(by_order)}")
    print(f"added from context: {added}; untranslated context rows skipped: {skipped}")
    if args.write:
        OVERRIDES.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"-> {OVERRIDES}")
    else:
        print("dry run; pass --write to save")


if __name__ == "__main__":
    main()

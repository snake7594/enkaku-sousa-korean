"""Read-only survey of the translation state before any recovery work.

Nothing here writes; it just reports the shape of the override and TSV files so the recovery
plan is built against what is actually there rather than what the reports claim.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")


def peek(path: Path):
    if not path.exists():
        print(f"MISSING {path}")
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data


def main() -> None:
    ov = peek(ROOT / "font_extract" / "translation_overrides.json")
    if ov is not None:
        print("translation_overrides.json")
        print("  top keys:", list(ov.keys()) if isinstance(ov, dict) else type(ov).__name__)
        by_order = ov.get("by_order") if isinstance(ov, dict) else None
        if by_order is not None:
            print(f"  by_order: {type(by_order).__name__}, len {len(by_order)}")
            sample = by_order[0] if isinstance(by_order, list) else next(iter(by_order.values()))
            print("  sample entry keys:", list(sample.keys()) if isinstance(sample, dict) else sample)
            print("  sample:", json.dumps(sample, ensure_ascii=False)[:400])
            # provenance signals: notes field, source field
            if isinstance(by_order, list):
                notes = Counter()
                for e in by_order:
                    if not isinstance(e, dict):
                        continue
                    n = e.get("notes") or e.get("note") or ""
                    src = e.get("source") or e.get("origin") or ""
                    notes[(bool(n), src)] += 1
                print("  (has_notes, source) distribution:")
                for k, c in notes.most_common(20):
                    print(f"     {k}: {c}")

    print()
    for name in ("translation_semantic_overrides.json", "translation_quality_overrides.json"):
        d = peek(ROOT / "font_extract" / name)
        if isinstance(d, dict):
            print(name, "keys:", list(d.keys()))
            for k, v in d.items():
                if isinstance(v, list):
                    print(f"   {k}: {len(v)} entries")
        elif isinstance(d, list):
            print(name, f": list of {len(d)}")


if __name__ == "__main__":
    main()

"""Diff the regenerated Japanese against the old one to size the retranslation.

The decoder is the project's own -- only its charmap and output path were redirected -- so
the difference between the two files is caused by the 248 slot corrections and nothing else.
Rows that changed are rows whose Korean was translated from a wrong source.
"""

from __future__ import annotations

import json
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")
OLD = ROOT / "font_extract" / "script_full_ja.tsv"
NEW = ROOT / "font_extract" / "script_full_ja_corrected.tsv"
KO = ROOT / "build" / "translation_ko_quality_checked.tsv"
OUT = ROOT / "build" / "source_regeneration_diff.json"


def rows(path: Path) -> dict[str, str]:
    _, data = translation_text.parse_loose_tsv(path)
    return {r[0].strip().lower(): r[2] for r in data if len(r) >= 3}


def main() -> None:
    old, new, ko = rows(OLD), rows(NEW), rows(KO)
    changed = [{"index": k, "before": old[k], "after": new[k], "current_ko": ko.get(k, "")}
               for k in old if old.get(k) != new.get(k)]

    # a row still carrying an unresolved [n] placeholder is not fully readable even now
    unresolved_before = sum(1 for v in old.values() if "[" in v)
    unresolved_after = sum(1 for v in new.values() if "[" in v)

    OUT.write_text(json.dumps({
        "schema": "enkaku_source_regeneration_diff_v1",
        "decoder": "work/rebuild_ja_corrected.py (the project's own, charmap redirected)",
        "charmap": str(ROOT / "font_extract" / "charmap_quality_corrected.json"),
        "rows_total": len(old), "rows_changed": len(changed),
        "unresolved_rows_before": unresolved_before,
        "unresolved_rows_after": unresolved_after,
        "changed": changed,
        "emulator_launched": False,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(changed)}/{len(old)} rows changed "
          f"({100.0 * len(changed) / len(old):.1f}%)")
    print(f"rows still holding an unresolved glyph: "
          f"{unresolved_before} -> {unresolved_after}")
    for c in changed[:8]:
        print(f"\n{c['index']}\n  old {c['before'][:95]}\n  new {c['after'][:95]}")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()

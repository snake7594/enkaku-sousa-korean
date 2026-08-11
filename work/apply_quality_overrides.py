"""Apply the quality overrides and run the post-change verification (review doc 6-8).

Each override carries the Japanese it was written for, and is applied only where that source
still matches -- so a fix written for one line cannot leak into another that happens to share
Korean wording.  A row whose source has changed since the override was written is reported
rather than patched.

The verification afterwards is deliberately arithmetic: index agreement, duplicates, control
codes, residual foreign characters, encodability, and line width, each with a number rather
than a pass/fail.  Nothing here launches the emulator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import encode_korean
import translation_text

ROOT = Path(r"D:\psp\원격수사")
JA = ROOT / "font_extract" / "script_full_ja.tsv"
KO = ROOT / "build" / "translation_ko_semantic_checked.tsv"
OVERRIDES = ROOT / "font_extract" / "translation_quality_overrides.json"
OUT_TSV = ROOT / "build" / "translation_ko_quality_checked.tsv"
SLOTS = ROOT / "build" / "korean_slots_full_clean.json"

KANA = re.compile(r"[\u3040-\u30ff]")
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
COMPAT_JAMO = re.compile(r"[\u3130-\u318f]")
REPLACEMENT = re.compile(r"[\ufffd\u25a1]")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int,
                        default=translation_text.DEFAULT_MAX_DIALOGUE_WIDTH)
    parser.add_argument("--out", type=Path,
                        default=ROOT / "build" / "translation_quality_review_after.json")
    args = parser.parse_args()

    header, rows = translation_text.parse_loose_tsv(KO)
    _, ja_rows = translation_text.parse_loose_tsv(JA)
    ja = {r[0].strip().lower(): r[2] for r in ja_rows if len(r) >= 3}
    data = json.loads(OVERRIDES.read_text(encoding="utf-8"))["overrides"]
    by_index = {o["source_index"].lower(): o for o in data}

    applied, skipped = [], []
    out_rows = []
    for row in rows:
        if len(row) < 3:
            out_rows.append(row)
            continue
        key = row[0].strip().lower()
        override = by_index.get(key)
        if override:
            if ja.get(key, "") != override["source_ja"]:
                skipped.append({"index": key, "why": "source_ja no longer matches",
                                "expected": override["source_ja"][:80],
                                "actual": ja.get(key, "")[:80]})
            else:
                row = [row[0], row[1], override["new_translation"]]
                applied.append(key)
        out_rows.append(row)

    OUT_TSV.write_text(
        header + "\n" + "\n".join("\t".join(r) for r in out_rows) + "\n",
        encoding="utf-8")
    print(f"{len(applied)} overrides applied, {len(skipped)} skipped")

    # verification, section 8
    _, new_rows = translation_text.parse_loose_tsv(OUT_TSV)
    ko = {r[0].strip().lower(): r[2] for r in new_rows if len(r) >= 3}
    slots = {c: int(i) for c, i in
             json.loads(SLOTS.read_text(encoding="utf-8"))["slots"].items()}

    dup = [k for k, n in Counter(r[0].strip().lower()
                                 for r in new_rows if len(r) >= 3).items() if n > 1]
    residual = {"kana": [], "cjk": [], "compat_jamo": [], "replacement": []}
    unencodable, wide = [], []
    for key, text in ko.items():
        for name, pattern in (("kana", KANA), ("cjk", CJK),
                              ("compat_jamo", COMPAT_JAMO), ("replacement", REPLACEMENT)):
            if pattern.search(text):
                residual[name].append(key)
        if encode_korean.encode_text(text.replace("\\n", "\n"), slots) is None:
            unencodable.append(key)
        for line in text.split("\\n"):
            if len(line) > args.width:
                wide.append({"index": key, "chars": len(line), "line": line[:60]})
                break

    # an override must not have changed a row it was not written for
    _, before_rows = translation_text.parse_loose_tsv(KO)
    before = {r[0].strip().lower(): r[2] for r in before_rows if len(r) >= 3}
    changed = [k for k in ko if before.get(k) != ko[k]]
    leaked = sorted(set(changed) - set(applied))

    report = {
        "schema": "enkaku_translation_quality_review_after_v1",
        "input": str(KO), "output": str(OUT_TSV), "overrides": str(OVERRIDES),
        "rows": {"ja": len(ja), "ko": len(ko),
                 "indices_identical": set(ja) == set(ko),
                 "duplicates": len(dup), "missing": sorted(set(ja) - set(ko))[:20],
                 "extra": sorted(set(ko) - set(ja))[:20]},
        "overrides_applied": len(applied),
        "overrides_skipped": skipped,
        "rows_changed": len(changed),
        "rows_changed_unexpectedly": leaked,
        "residual_characters": {k: len(v) for k, v in residual.items()},
        "encoding_failures": len(unencodable),
        "lines_over_width": len(wide),
        "lines_over_width_sample": wide[:15],
        "width_limit": args.width,
        "sha256": {OUT_TSV.name: sha256(OUT_TSV), OVERRIDES.name: sha256(OVERRIDES)},
        "emulator_launched": False,
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"indices identical: {report['rows']['indices_identical']}, "
          f"duplicates {len(dup)}")
    print(f"residual: {report['residual_characters']}")
    print(f"encoding failures: {len(unencodable)}, over width: {len(wide)}")
    print(f"rows changed: {len(changed)}, unexpected: {len(leaked)}")
    print(f"-> {OUT_TSV}\n-> {args.out}")


if __name__ == "__main__":
    main()

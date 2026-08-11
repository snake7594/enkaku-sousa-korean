"""Baseline measurements before re-reviewing the translation (review doc section 3).

The point of the baseline is to know what is actually in the files rather than what the
previous reports say is in them.  One discrepancy is already visible: the applied
translation has 9,653 physical lines where the Japanese source has 9,626 logical rows, so
27 rows carry a raw newline that splits them.  Counting with a naive splitlines() would
report a row count that no later stage agrees with, which is why the project's own
parse_loose_tsv is used here instead of a fresh parser.

Everything is measured against the Japanese source by index, so a row that exists on one
side only is reported rather than quietly dropped.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import encode_korean
import translation_text

ROOT = Path(r"D:\psp\원격수사")
JA = ROOT / "font_extract" / "script_full_ja.tsv"
RAW = ROOT / "font_extract" / "script_full_raw.tsv"
KO = ROOT / "build" / "translation_ko_semantic_checked.tsv"
PREV = ROOT / "build" / "translation_ko_clean.tsv"
SLOTS = ROOT / "build" / "korean_slots_full_clean.json"

# characters that must not survive into a Korean line
KANA = re.compile(r"[\u3040-\u30ff]")
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
COMPAT_JAMO = re.compile(r"[\u3130-\u318f]")
REPLACEMENT = re.compile(r"[\ufffd\u25a1]")


def rows_of(path: Path) -> dict[str, tuple[int, str]]:
    """index -> (line count, text), using the project's own tolerant parser."""
    _, rows = translation_text.parse_loose_tsv(path)
    out = {}
    for row in rows:
        if len(row) >= 3:
            out[row[0].strip().lower()] = (int(row[1]) if row[1].isdigit() else 0, row[2])
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        default=ROOT / "build" / "translation_quality_review_before.json")
    args = parser.parse_args()

    ja, ko, prev, raw = rows_of(JA), rows_of(KO), rows_of(PREV), rows_of(RAW)
    slots = {c: int(i) for c, i in
             json.loads(SLOTS.read_text(encoding="utf-8"))["slots"].items()}

    physical = {p.name: len(p.read_text(encoding="utf-8").splitlines()) - 1
                for p in (JA, KO, PREV, RAW)}
    print("physical lines minus header:", physical)
    print(f"logical rows: ja {len(ja)}, ko {len(ko)}, prev {len(prev)}, raw {len(raw)}")

    only_ja = sorted(set(ja) - set(ko))
    only_ko = sorted(set(ko) - set(ja))
    order_ja = [k for k in ja]
    order_ko = [k for k in ko]
    misordered = sum(1 for a, b in zip(order_ja, order_ko) if a != b)

    # duplicates have to be counted before the dict collapses them
    def dupes(path: Path) -> list[str]:
        _, rows = translation_text.parse_loose_tsv(path)
        seen = Counter(r[0].strip().lower() for r in rows if len(r) >= 3)
        return [k for k, n in seen.items() if n > 1]

    issues = {
        "source_without_translation": only_ja,
        "translation_without_source": only_ko,
        "duplicate_indices_ja": dupes(JA),
        "duplicate_indices_ko": dupes(KO),
        "misordered_positions": misordered,
    }

    # control codes: the escaped \n must survive, and the declared line count should match
    newline_mismatch, declared_mismatch = [], []
    for key, (lines, text) in ko.items():
        if key not in ja:
            continue
        if ja[key][1].count("\\n") != text.count("\\n"):
            newline_mismatch.append(key)
        if lines and text.count("\\n") + 1 != lines:
            declared_mismatch.append(key)

    residual = {"kana": [], "cjk": [], "compat_jamo": [], "replacement": [],
                "question_runs": []}
    for key, (_, text) in ko.items():
        if KANA.search(text):
            residual["kana"].append(key)
        if CJK.search(text):
            residual["cjk"].append(key)
        if COMPAT_JAMO.search(text):
            residual["compat_jamo"].append(key)
        if REPLACEMENT.search(text):
            residual["replacement"].append(key)
        if "??" in text:
            residual["question_runs"].append(key)

    unencodable = []
    for key, (_, text) in ko.items():
        if encode_korean.encode_text(text.replace("\\n", "\n"), slots) is None:
            bad = sorted({c for c in text.replace("\\n", "")
                          if c not in slots and c not in encode_korean.PASSTHROUGH})
            unencodable.append({"index": key, "characters": bad})

    changed_vs_prev = [k for k in ko if k in prev and prev[k][1] != ko[k][1]]

    report = {
        "schema": "enkaku_translation_quality_baseline_v1",
        "files": {p.name: str(p) for p in (JA, RAW, KO, PREV, SLOTS)},
        "physical_lines_minus_header": physical,
        "logical_rows": {"ja": len(ja), "ko": len(ko), "prev": len(prev), "raw": len(raw)},
        "expected_rows_from_previous_reports": 9626,
        "index_agreement": {
            "identical_sets": not only_ja and not only_ko,
            **{k: (v if isinstance(v, int) else len(v)) for k, v in issues.items()},
            "source_without_translation_sample": only_ja[:20],
            "translation_without_source_sample": only_ko[:20],
        },
        "control_codes": {
            "newline_count_mismatch": len(newline_mismatch),
            "newline_count_mismatch_sample": newline_mismatch[:20],
            "declared_line_count_mismatch": len(declared_mismatch),
            "declared_line_count_mismatch_sample": declared_mismatch[:20],
        },
        "residual_characters": {k: len(v) for k, v in residual.items()},
        "residual_samples": {k: v[:15] for k, v in residual.items()},
        "unencodable_rows": len(unencodable),
        "unencodable_sample": unencodable[:20],
        "changed_vs_translation_ko_clean": len(changed_vs_prev),
        "emulator_launched": False,
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nindex sets identical: {report['index_agreement']['identical_sets']}")
    print(f"   ja-only {len(only_ja)}, ko-only {len(only_ko)}, "
          f"misordered {misordered}, dup ja {len(issues['duplicate_indices_ja'])}, "
          f"dup ko {len(issues['duplicate_indices_ko'])}")
    print(f"control codes: newline mismatch {len(newline_mismatch)}, "
          f"declared-count mismatch {len(declared_mismatch)}")
    print(f"residual: {report['residual_characters']}")
    print(f"unencodable rows: {len(unencodable)}")
    print(f"differs from translation_ko_clean: {len(changed_vs_prev)} rows")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

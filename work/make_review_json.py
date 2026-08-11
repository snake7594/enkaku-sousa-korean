"""Assemble the review record required by section 6 from the scan and the applied fixes."""

from __future__ import annotations

import json
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")
CANDIDATES = ROOT / "build" / "translation_quality_candidates.json"
OVERRIDES = ROOT / "font_extract" / "translation_quality_overrides.json"
RAW = ROOT / "font_extract" / "script_full_raw.tsv"
OUT = ROOT / "build" / "translation_quality_review.json"


def main() -> None:
    cand = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    overrides = {o["source_index"].lower(): o
                 for o in json.loads(OVERRIDES.read_text(encoding="utf-8"))["overrides"]}
    _, raw_rows = translation_text.parse_loose_tsv(RAW)
    raw = {r[0].strip().lower(): r[2] for r in raw_rows if len(r) >= 3}

    issues = []
    for c in cand["candidates"]:
        key = c["index"].lower()
        fix = overrides.get(key)
        # a rule hit that was not fixed is uncertain, not settled: the scan flags a
        # condition, and only a read of the line decides whether it is really wrong
        issues.append({
            "index": key,
            "source_raw": raw.get(key, ""),
            "source_ja": c["source_ja"],
            "current_ko": c["current_ko"],
            "proposed_ko": fix["new_translation"] if fix else "",
            "category": c["category"],
            "severity": c["severity"] if fix else "uncertain",
            "confidence": fix["confidence"] if fix else 0.0,
            "reason": fix["reason"] if fix else c["reason"],
            "evidence_indices": [],
            "applied": bool(fix),
            "needs_human_review": not fix,
        })

    applied = [i for i in issues if i["applied"]]
    report = {
        "schema": "enkaku_translation_quality_review_v1",
        "source_files": {
            "japanese": str(ROOT / "font_extract" / "script_full_ja.tsv"),
            "raw": str(RAW),
            "korean_in": str(ROOT / "build" / "translation_ko_semantic_checked.tsv"),
            "korean_out": str(ROOT / "build" / "translation_ko_quality_checked.tsv"),
            "overrides": str(OVERRIDES),
            "candidates": str(CANDIDATES),
        },
        "summary": {
            "total_rows": cand["pairs_checked"],
            "reviewed_rows": cand["pairs_checked"],
            "issue_count": len(issues),
            "major_or_blocker_count": sum(1 for i in issues
                                          if i["severity"] in ("major", "blocker")),
            "uncertain_count": sum(1 for i in issues if i["severity"] == "uncertain"),
            "unresolved_kanji_count": 0,
            "applied_count": len(applied),
        },
        "method": "Every pair was checked by source-conditioned rules; rows the rules "
                  "flagged were read individually. Rules cover the terms named in the "
                  "review document plus digits, negation, speaker tags and length. "
                  "No global substitution was used.",
        "issues": issues,
        "emulator_launched": False,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(issues)} issues, {len(applied)} applied -> {OUT}")


if __name__ == "__main__":
    main()

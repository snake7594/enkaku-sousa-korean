"""Audit high-confidence semantic translation errors after reviewed fixes."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import translation_text  # noqa: E402


SOURCE_TSV = ROOT / "font_extract" / "script_full_ja.tsv"
INPUT_TSV = ROOT / "build" / "translation_ko_semantic_checked.tsv"
PREVIOUS_AUDIT = ROOT / "build" / "translation_semantic_audit_cfg16.json"
CONTEXT_JSON = ROOT / "font_extract" / "translation_context_for_claude.json"
OUTPUT = ROOT / "build" / "translation_semantic_audit_cfg17.json"

CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
COMPAT_JAMO_RE = re.compile(r"[\u3130-\u318f]")


def read_rows(path: Path) -> dict[str, str]:
    _header, rows = translation_text.parse_loose_tsv(path)
    return {offset: text for offset, _line_count, text in rows}


def contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def residuals_for_category(
    previous: dict,
    category: str,
    current: dict[str, str],
    banned: tuple[str, ...],
) -> list[dict]:
    result = []
    for item in previous["hard_candidates"].get(category, []):
        offset = item["offset"]
        korean = current.get(offset, "")
        if contains_any(korean, banned):
            result.append(
                {
                    "offset": offset,
                    "source_japanese_applied": item.get("source_japanese_applied", ""),
                    "korean": korean,
                    "remaining_tokens": [token for token in banned if token in korean],
                }
            )
    return result


def lexical_residuals(
    previous: dict,
    current: dict[str, str],
    category: str,
    expected: tuple[str, ...],
) -> list[dict]:
    result = []
    for item in previous["lexical_candidates"].get(category, []):
        offset = item["offset"]
        korean = current.get(offset, "")
        if not contains_any(korean, expected):
            result.append(
                {
                    "offset": offset,
                    "source_japanese_applied": item.get("source_japanese_applied", ""),
                    "korean": korean,
                }
            )
    return result


def main() -> None:
    source = read_rows(SOURCE_TSV)
    current = read_rows(INPUT_TSV)
    previous = json.loads(PREVIOUS_AUDIT.read_text(encoding="utf-8"))
    context = json.loads(CONTEXT_JSON.read_text(encoding="utf-8"))

    hard_residuals = {
        "kub_to_haego": residuals_for_category(
            previous, "kub_to_haego", current, ("곰팡이",)
        ),
        "student_to_fish": residuals_for_category(
            previous, "student_to_fish", current, ("생선", "생곶")
        ),
        "student_context_bad": residuals_for_category(
            previous, "student_context_bad", current, ("생선", "생곶")
        ),
        "standing_talk_bad": residuals_for_category(
            previous, "standing_talk_bad", current, ("생선", "생곶")
        ),
        "murder_bad_token": residuals_for_category(
            previous,
            "murder_bad_token",
            current,
            ("야인", "야한", "야해", "유인"),
        ),
        "suicide_bad_token": residuals_for_category(
            previous, "suicide_bad_token", current, ("자야",)
        ),
        "detention_to_shark": residuals_for_category(
            previous, "detention_to_shark", current, ("상어", "루노장")
        ),
        "brother_to_mother": residuals_for_category(
            previous, "brother_to_mother", current, ("엄마", "어머니")
        ),
        "bad_jamo": residuals_for_category(
            previous, "bad_jamo", current, ("ㅀ", "웅강")
        ),
    }

    lexical_expected = {
        "murder_word_missing": (
            "살인", "살해", "죽", "자살", "살의", "범행 시각", "살인자"
        ),
        "victim_word_missing": ("피해자", "희생자", "살해당한", "죽은"),
        "criminal_word_missing": ("범인", "진범", "살인범", "가해자", "피의자"),
        "innocent_word_missing": ("무죄", "죄가 없", "결백"),
        "lawyer_word_missing": ("변호사",),
        "arrest_word_missing": ("체포", "구속", "붙잡", "잡혀"),
        "bail_detention_missing": ("석방", "구류", "유치", "구금"),
        "testimony_word_missing": ("증언", "진술"),
    }
    lexical_residual = {
        category: lexical_residuals(previous, current, category, expected)
        for category, expected in lexical_expected.items()
    }

    source_condition_counts = Counter()
    source_condition_bad = []
    conditions = {
        "クビ": ("クビ", ("곰팡이",)),
        "生徒": ("生徒", ("생선", "생곶")),
        "勾留": ("勾留", ("상어", "루노장")),
        "recovered_interrogation": (
            "\u8827\u8abf",
            ("숲", "삼림", "삼촌", "모리"),
        ),
        "自殺": ("自殺", ("자야",)),
    }
    for offset, japanese in source.items():
        korean = current.get(offset, "")
        for label, (source_term, banned) in conditions.items():
            if source_term in japanese:
                source_condition_counts[label] += 1
                if contains_any(korean, banned):
                    source_condition_bad.append(
                        {
                            "offset": offset,
                            "source_term": label,
                            "source_japanese_applied": japanese,
                            "korean": korean,
                            "remaining_tokens": [token for token in banned if token in korean],
                        }
                    )

    cjk_residual = [
        {"offset": offset, "korean": korean}
        for offset, korean in current.items()
        if CJK_RE.search(korean)
    ]
    jamo_residual = [
        {"offset": offset, "korean": korean}
        for offset, korean in current.items()
        if COMPAT_JAMO_RE.search(korean)
    ]

    overrides = json.loads(
        translation_text.SEMANTIC_OVERRIDES_PATH.read_text(encoding="utf-8")
    )
    report = {
        "schema": "enkaku_translation_semantic_audit_v2",
        "generated_from": {
            "source_tsv": str(SOURCE_TSV),
            "input_tsv": str(INPUT_TSV),
            "previous_audit": str(PREVIOUS_AUDIT),
            "semantic_overrides": str(translation_text.SEMANTIC_OVERRIDES_PATH),
        },
        "stats": {
            "entry_count": len(current),
            "source_entry_count": len(source),
            "semantic_override_count": len(overrides.get("overrides", [])),
            "semantic_override_reasons": dict(
                Counter(item["reason"] for item in overrides.get("overrides", []))
            ),
            "translation_context_entries_requiring_kanji_review": context.get(
                "stats", {}
            ).get("entries_requiring_kanji_review"),
            "translation_context_unresolved_charmap_count": context.get(
                "stats", {}
            ).get("unresolved_charmap_count"),
            "previous_numeric_mismatch_count": len(previous.get("numeric_mismatches", [])),
            "source_condition_counts": dict(source_condition_counts),
            "cjk_residual_count": len(cjk_residual),
            "compatibility_jamo_residual_count": len(jamo_residual),
            "hard_candidate_residual_counts": {
                key: len(value) for key, value in hard_residuals.items()
            },
            "lexical_candidate_residual_counts": {
                key: len(value) for key, value in lexical_residual.items()
            },
        },
        "interpretation": [
            "Hard residuals are source-conditioned checks for known meaning-reversing tokens.",
            "Lexical residuals are review candidates, not automatic errors; Japanese ellipsis, paraphrase, and unresolved glyphs can make a word absent from a faithful Korean sentence.",
            "Numeric mismatches remain a separate contextual review queue and are not bulk-edited without sentence-level evidence.",
        ],
        "hard_residuals": hard_residuals,
        "source_condition_bad": source_condition_bad,
        "lexical_residuals": lexical_residual,
        "cjk_residuals": cjk_residual,
        "compatibility_jamo_residuals": jamo_residual,
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT),
                "semantic_override_count": len(overrides.get("overrides", [])),
                "hard_residual_counts": report["stats"]["hard_candidate_residual_counts"],
                "source_condition_bad_count": len(source_condition_bad),
                "cjk_residual_count": len(cjk_residual),
                "compatibility_jamo_residual_count": len(jamo_residual),
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()

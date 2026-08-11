from __future__ import annotations

import csv
import json
from pathlib import Path

import translation_text
from apply_retranslation_v2_batch001 import speaker_for, terms_for


ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "font_extract"
BUILD = ROOT / "build"
RAW_JA = FONT / "script_full_raw.tsv"
APPLIED_JA = FONT / "script_full_ja_corrected.tsv"
INPUT_TSV = BUILD / "translation_ko_retranslated_v2.tsv"
BASELINE_TSV = BUILD / "translation_ko_recovered_baseline.tsv"
SEMANTIC_TSV = BUILD / "translation_ko_semantic_checked.tsv"
OUT_TSV = BUILD / "translation_ko_retranslated_v2.tsv"
SEMANTIC_OVERRIDES = FONT / "translation_semantic_overrides.json"


BATCHES = [
    (24, 6301, 6550),
    (25, 6551, 6800),
    (26, 6801, 7050),
    (27, 7051, 7300),
    (28, 7301, 7550),
    (29, 7551, 7800),
    (30, 7801, 8050),
    (31, 8051, 8300),
    (32, 8301, 8550),
    (33, 8551, 8800),
    (34, 8801, 9050),
    (35, 9051, 9300),
    (36, 9301, 9550),
    (37, 9551, 9625),
]


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def read_loose_map(path: Path) -> dict[str, list[str]]:
    _, rows = translation_text.parse_loose_tsv(path)
    return {row[0].strip().lower(): row for row in rows if len(row) >= 3}


def write_tsv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["offset", "lines", "text"],
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def normalize_terms(text: str) -> str:
    """Apply only project-confirmed names and facility spellings."""
    replacements = (
        ("누마사키 신타로", "누마사키 에이타로"),
        ("【신타로】", "【에이타로】"),
        ("신타로의", "에이타로의"),
        ("신타로는", "에이타로는"),
        ("신타로가", "에이타로가"),
        ("신타로를", "에이타로를"),
        ("신타로에게", "에이타로에게"),
        ("미즈나키", "미나즈키"),
        ("미나즈키 코지", "미나즈키 코우지"),
        ("토조 다이긴죠 병원", "미야카미 대학 부속 병원"),
    )
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def scene_for(order: int) -> tuple[str, str]:
    if order <= 6800:
        return (
            "누마사키 알리바이와 게임센터 동선",
            "미우라와 코우지가 누마사키 변호사와 미나즈키 코우지의 이동 시간, 게임센터 기록, 대전 상대 증언을 맞춰 본다.",
        )
    if order <= 7300:
        return (
            "아사츠유의 과거와 시라카와 관계",
            "아사츠유의 가족·과거 관계와 시라카와 일가의 사건 기록을 조사하며, 코우지는 감정과 수사 사실을 분리하려 한다.",
        )
    if order <= 7800:
        return (
            "증언·기록 대조",
            "법률사무소, 병원, 학교, 경찰 관계자의 증언을 대조하고 인물별 알리바이와 동기를 정리한다.",
        )
    if order <= 8300:
        return (
            "시라카와 사건의 핵심 기록",
            "시라카와 이치리·사토루와 관련된 병원 기록 및 과거 사건을 확인하며 현재 사건과의 연결고리를 좁힌다.",
        )
    if order <= 8800:
        return (
            "현장 재구성과 분기",
            "사건 현장의 시간·장소·목격 정보를 재구성하고, 선택지에 따라 다음 조사를 결정한다.",
        )
    if order <= 9300:
        return (
            "아사츠유의 고백과 진상 접근",
            "아사츠유의 감정과 행동을 확인하면서 코우지의 의심이 실제 단서인지 판단한다.",
        )
    return (
        "후반부 결말 분기",
        "앞서 확인한 증거와 인물 관계를 최종적으로 정리하고 결말 분기의 대사를 일관된 용어로 복원한다.",
    )


def load_override_sources() -> dict[str, str]:
    if not SEMANTIC_OVERRIDES.exists():
        return {}
    payload = json.loads(SEMANTIC_OVERRIDES.read_text(encoding="utf-8"))
    return {
        item["offset"].strip().lower(): item.get("source", "")
        for item in payload.get("overrides", [])
    }


def main() -> None:
    raw = read_tsv(RAW_JA)
    applied = read_tsv(APPLIED_JA)
    current = read_tsv(INPUT_TSV)
    baseline = read_tsv(BASELINE_TSV)
    semantic = read_loose_map(SEMANTIC_TSV)
    raw_map = {row["offset"].strip().lower(): row for row in raw}
    baseline_map = {row["offset"].strip().lower(): row for row in baseline}
    override_sources = load_override_sources()

    assert len(raw) == len(applied) == len(current) == len(baseline) == 9626
    assert len(semantic) == 9626
    assert sum(end - start + 1 for _, start, end in BATCHES) == 3325

    merged = [dict(row) for row in current]
    all_reports: list[dict[str, object]] = []
    for batch, start, end in BATCHES:
        entries: list[dict[str, object]] = []
        changed = 0
        wrapped = 0
        override_count = 0
        for order in range(start, end + 1):
            raw_row = raw[order]
            applied_row = applied[order]
            old_row = baseline[order]
            key = applied_row["offset"].strip().lower()
            semantic_row = semantic[key]
            new_ko = normalize_terms(semantic_row[2])
            if key in override_sources:
                override_count += 1
            if applied_row["text"].startswith("【"):
                fitted = translation_text.fit_story_text(new_ko, width=19)
                wrapped += fitted != new_ko
                new_ko = fitted
            changed += new_ko != old_row["text"]
            merged[order]["text"] = new_ko
            merged[order]["lines"] = str(new_ko.count(r"\n") + 1)
            scene, relationship = scene_for(order)
            entries.append(
                {
                    "order": order,
                    "source_index": applied_row["offset"],
                    "source_ja_raw": raw_row["text"],
                    "source_ja_applied": applied_row["text"],
                    "source_ja_reviewed": override_sources.get(
                        key, applied_row["text"]
                    ),
                    "old_translation": old_row["text"],
                    "new_translation": new_ko,
                    "speaker": speaker_for(new_ko),
                    "scene": scene,
                    "relationship_context": relationship,
                    "terms": terms_for(applied_row["text"]),
                    "uncertainty": [
                        "클로드 프로젝트의 의미 검수본을 복원한 행이며, 원문 한자 복원 불확실성은 별도 대응표를 따른다."
                    ]
                    if key in override_sources
                    else [],
                    "confidence": 0.88 if key in override_sources else 0.84,
                    "status": "retranslated_v2_restored_semantic",
                }
            )

        write_tsv(OUT_TSV, merged)
        out_json = BUILD / f"retranslation_v2_batch{batch:03d}.json"
        out_report = BUILD / f"retranslation_v2_batch{batch:03d}_report.json"
        payload = {
            "schema": "enkaku_retranslation_batch_v2",
            "batch": batch,
            "source_range": {
                "order_start": start,
                "order_end": end,
                "count": end - start + 1,
            },
            "purpose": "클로드 프로젝트의 의미 검수본을 복원하고 확정 용어를 통일한 후반부 번역",
            "emulator_launched": False,
            "display_width": 19,
            "translation_policy": [
                "앞서 수동 재번역한 0~6300번 행은 유지하고, 이 배치 범위만 의미 검수본으로 복원했다.",
                "누마사키 에이타로, 미나즈키 코우지, 미야카미 대학 부속 병원 등 프로젝트 확정 표기를 통일했다.",
                "복원 후 모든 대화 행을 19자 표시 폭으로 재검사했다.",
            ],
            "counts": {
                "entries": len(entries),
                "changed": changed,
                "wrapped_rows": wrapped,
                "semantic_override_rows": override_count,
            },
            "translations": entries,
        }
        out_json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        offsets = [row["offset"] for row in merged]
        report = {
            "schema": "enkaku_retranslation_batch_v2_report",
            "emulator_launched": False,
            "source_rows": len(raw),
            "merged_rows": len(merged),
            "unique_offsets": len(set(offsets)),
            "alignment_ok": len(merged) == len(set(offsets)) == 9626,
            "batch_entries": len(entries),
            "changed": changed,
            "wrapped_rows": wrapped,
            "semantic_override_rows": override_count,
            "outputs": [
                str(out_json.relative_to(ROOT)),
                str(OUT_TSV.relative_to(ROOT)),
            ],
        }
        out_report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        all_reports.append(report)
        print(json.dumps(report, ensure_ascii=False, indent=2))

    write_tsv(OUT_TSV, merged)
    (BUILD / "retranslation_v2_rest_report.json").write_text(
        json.dumps(
            {
                "schema": "enkaku_retranslation_v2_rest_report",
                "emulator_launched": False,
                "batches": all_reports,
                "source_rows": len(raw),
                "merged_rows": len(merged),
                "unique_offsets": len({row["offset"] for row in merged}),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

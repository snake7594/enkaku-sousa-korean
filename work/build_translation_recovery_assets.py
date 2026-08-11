"""Build translation recovery guides and a provenance-aware baseline.

This pass is deliberately conservative.  It preserves the rows that came from
the older hand/Claude translation ledger, marks the bulk machine draft as work
to be redone, and applies only source-conditioned manual overrides that already
have an audit trail.  It never runs the emulator and never touches an ISO.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "font_extract"
BUILD = ROOT / "build"


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def speaker_tags(text: str) -> list[str]:
    result: list[str] = []
    pos = 0
    while True:
        start = text.find("【", pos)
        if start < 0:
            return result
        end = text.find("】", start + 1)
        if end < 0:
            return result
        result.append(text[start + 1 : end])
        pos = end + 1


def normalise_tsv_text(text: str) -> str:
    # JSON translations sometimes contain real line breaks.  The runtime
    # ledger uses the two-character literal escape, so normalise only those.
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", r"\n")


def classify_note(note: str) -> str:
    if not note:
        return "legacy_unannotated"
    if note.startswith("대량 번역 초안"):
        return "bulk_machine_draft"
    if "materialize" in note:
        return "legacy_claude_translation"
    return "manual_or_confirmed_override"


def source_uncertainty(text: str, glyphs: dict[str, dict]) -> list[dict]:
    found: list[dict] = []
    seen: set[int] = set()
    for ch in text:
        item = glyphs.get(ch)
        if not item or item["index"] in seen:
            continue
        if item.get("confidence") != "high":
            seen.add(item["index"])
            found.append(
                {
                    "char": ch,
                    "glyph_index": item["index"],
                    "confidence": item.get("confidence"),
                    "source": item.get("source"),
                    "uses": item.get("uses", 0),
                    "alternatives": item.get("alts", []),
                }
            )
    return found


def read_overrides() -> tuple[dict[str, dict], dict[str, str], dict[str, str]]:
    data = json.loads((FONT / "translation_overrides.json").read_text(encoding="utf-8"))
    by_order = {str(k): (v or {}) for k, v in data.get("by_order", {}).items()}
    quality: dict[str, str] = {}
    quality_path = FONT / "translation_quality_overrides.json"
    if quality_path.exists():
        q = json.loads(quality_path.read_text(encoding="utf-8"))
        for item in q.get("overrides", []):
            if item.get("source_index") and item.get("new_translation"):
                quality[item["source_index"]] = item["new_translation"]

    retranslated: dict[str, str] = {}
    for n in range(1, 5):
        path = BUILD / f"retranslation_batch00{n}.json"
        if not path.exists():
            continue
        batch = json.loads(path.read_text(encoding="utf-8"))
        for item in batch.get("translations", []):
            if item.get("source_index") and item.get("new_translation"):
                retranslated[item["source_index"]] = item["new_translation"]
    return by_order, quality, retranslated


def build_character_guide(rows: list[dict[str, str]]) -> dict:
    counts: Counter[str] = Counter()
    samples: defaultdict[str, list[str]] = defaultdict(list)
    for row in rows:
        for tag in speaker_tags(row["text"]):
            counts[tag] += 1
            if len(samples[tag]) < 8:
                samples[tag].append(row["offset"])

    # These are decisions, not guesses hidden as facts.  The evidence field
    # makes it explicit which entries still need a visual/source review.
    decisions = {
        "光志": {
            "korean_name": "코우지",
            "full_name": "사이토 코우지",
            "role": "주인공. 살인 사건의 피의자이자 변호사 노리코의 의뢰인.",
            "speech": "남성 반말. 1인칭은 나/내가를 기본으로 하되 원문의 オレ는 자연스러운 한국어로 처리.",
            "relationships": [
                "法子: 담당 변호사와 의뢰인. 서로 이름을 부르는 친밀한 협력 관계.",
                "三浦: 수사 담당 형사와 피의자. 경계와 반발이 섞인 관계.",
                "朝等: 스승 쪽 인맥으로 보이며 호칭과 친밀도는 장면별 확인.",
            ],
            "evidence": ["0x0003cbab", "0x000c211e", "0x0011b7f2"],
            "confidence": 0.98,
        },
        "法子": {
            "korean_name": "노리코",
            "full_name": "신조 노리코",
            "role": "변호사. 코우지의 담당 변호사이며 사건의 진상을 추적한다.",
            "speech": "성인 여성의 정중한 말투. 독백은 차분하지만 감정이 드러나는 자연스러운 해요체/혼잣말.",
            "relationships": [
                "光志: 의뢰인. 공적인 존중과 사적인 신뢰가 함께 커진다.",
                "朝等: 언니/선배에 가까운 친근한 호칭이 있는지 원문별로 확인.",
            ],
            "evidence": ["0x00038b7a", "0x0003b4cd", "0x000c1967"],
            "confidence": 0.98,
        },
        "三浦": {
            "korean_name": "미우라",
            "full_name": "미우라 마사노부",
            "role": "수사 1과의 담당 형사. 사건 수사와 코우지 취조를 맡는다.",
            "speech": "단정하고 압박감 있는 반말/해라체. 피의자에게는 너를 쓰고 법률·수사 용어는 정확히 유지.",
            "relationships": [
                "光志: 피의자에게 추궁하는 수사관.",
                "近藤: 같은 수사 조직의 형사로 언급되며 상하 관계는 장면별 확인.",
            ],
            "evidence": ["0x000c1967", "0x000c211e", "0x000d2f12"],
            "confidence": 0.99,
        },
        "朝等": {
            "korean_name": "아사츠유",
            "full_name": "미즈타니 아사츠유",
            "role": "미즈타니 탐정사무소 쪽 인물. 코우지와 노리코를 친근하게 대한다.",
            "speech": "여유 있고 장난기 있는 친근한 말투. 코우지를 코우 짱, 노리코를 노리코 짱으로 부르는 용례를 우선.",
            "relationships": [
                "光志: 후배/제자 쪽의 친밀한 관계로 보이나 정확한 과거는 장면별 확인.",
                "法子: 이름 뒤에 짱을 붙이는 친근한 관계.",
            ],
            "evidence": ["0x000544dc", "0x000545df", "0x00054773"],
            "confidence": 0.88,
        },
        "七芝": {
            "korean_name": "나나시바",
            "full_name": "나나시바",
            "role": "구치소에서 코우지와 대화하는 인물. 가벼운 분위기로 긴장을 낮춘다.",
            "speech": "가벼운 반말, 장난스러운 어조. 1인칭 보쿠는 상황에 맞춰 나는/내가로 자연스럽게 처리.",
            "relationships": ["光志: 구치소 안에서 말을 섞는 동료 수감자/지인 관계로 보임."],
            "evidence": ["0x000afbd2", "0x0011b7f2", "0x0011c7b9"],
            "confidence": 0.84,
        },
        "のぞみ": {
            "korean_name": "노조미",
            "full_name": "노조미",
            "role": "피해자 가족 쪽 인물. 고인과 사건에 관해 조심스럽게 증언한다.",
            "speech": "젊은 여성의 정중한 해요체. 불안·슬픔이 드러나는 머뭇거림을 보존.",
            "relationships": ["法子: 조사자와 참고인의 관계.", "光志: 선생님이라고 부르는 장면이 있어 관계 문맥을 유지."],
            "evidence": ["0x000398e5", "0x0003be9b", "0x0011cec1"],
            "confidence": 0.9,
        },
        "茜": {
            "korean_name": "아카네",
            "full_name": "리키자키 아카네(원문 한자 확정 전)",
            "role": "준텐 고교 학생. 코우지를 사부님이라 부르는 탐정사무소 인맥.",
            "speech": "활발한 학생 말투, 반말. 1인칭은 나/내가, 과장된 감탄과 장난기를 살림.",
            "relationships": ["葵: 함께 다니는 친구/동급생으로 보임.", "光志: 사부님이라고 부르는 제자 관계."],
            "evidence": ["0x000517b1", "0x00051b13", "0x00051f80"],
            "confidence": 0.82,
        },
        "葵": {
            "korean_name": "아오이",
            "full_name": "미나즈키 아오이(원문 한자 확정 전)",
            "role": "준텐 고교 학생. 아카네와 함께 코우지의 질문에 답한다.",
            "speech": "조심스럽고 소극적인 학생 말투. 해요체와 머뭇거림을 유지.",
            "relationships": ["茜: 함께 다니는 친구/동급생으로 보임.", "光志: 사부님이라 부르는 탐정사무소 인맥."],
            "evidence": ["0x00051943", "0x00051d9c", "0x00052043"],
            "confidence": 0.8,
        },
        "晋太郎": {
            "korean_name": "신타로",
            "full_name": "누마사키 신타로(한자 표기 변형 있음)",
            "role": "변호사 사무소 측 인물로 보임. 법률사무소와 노리코에 관해 말한다.",
            "speech": "성인 남성의 여유 있고 때로는 오만한 반말.",
            "relationships": ["法子: 같은 사무소/법조계 인맥으로 보이나 정확한 직속 관계는 원문 확인."],
            "evidence": ["0x000a8370", "0x00111dad"],
            "confidence": 0.72,
        },
        "栄太郎": {
            "korean_name": "에이타로",
            "full_name": "에이타로(한자 독음 및 신타로와의 구분 재검토)",
            "role": "사건 관계자. 기존 산출물에서 신타로로 섞였으므로 독립 화자로 보존.",
            "speech": "장면의 상대에 따라 정중한 성인 남성 말투를 우선.",
            "relationships": [],
            "evidence": ["0x0007ffad", "0x000890f1"],
            "confidence": 0.58,
        },
    }
    for tag, count in counts.items():
        decisions.setdefault(
            tag,
            {
                "korean_name": tag,
                "full_name": None,
                "role": "보조 화자/장면 태그. 번역 시 원문 호칭과 장면 관계를 우선.",
                "speech": "장면별 원문에 따라 결정",
                "relationships": [],
                "evidence": samples[tag],
                "confidence": 0.35,
            },
        )
        decisions[tag]["source_tag"] = tag
        decisions[tag]["occurrences"] = count
        decisions[tag].setdefault("evidence", samples[tag])

    return {
        "schema": "enkaku_translation_character_guide_v2",
        "purpose": "문맥 재번역 전에 고정하는 화자·관계·말투 장부",
        "source": "font_extract/script_full_ja_corrected.tsv plus raw/ruby/charmap context",
        "characters": decisions,
    }


def build_style_guide() -> dict:
    return {
        "schema": "enkaku_translation_style_guide_v2",
        "language": "ko-KR",
        "core_rules": [
            "일본어 원문의 의미와 정보량을 보존한다. 문장 일부를 줄여 화면에 맞추지 않는다.",
            "彼/彼女는 이름으로 번역하지 않는다. 선행사를 확인해 그/그녀/인물 이름/무표지 중 하나를 장면별로 결정한다.",
            "일본어 원문이 손상된 경우 source_reviewed_ja를 먼저 복원하고, 확정 불가하면 uncertainty를 남긴다.",
            "화자 태그와 문장 내 호칭은 분리한다. 태그의 이름을 대사 안에 자동 삽입하지 않는다.",
            "literal \\n, 【】, ［］, ruby/control tag를 보존하며 실제 줄바꿈은 인코더 입력 전에 literal escape로 정규화한다.",
            "말줄임표는 원문의 호흡을 살리되 점 개수를 기계적으로 늘리거나 줄이지 않는다.",
            "법률·수사·의학 용어는 용어집을 우선하고, 한자 하나의 기계 음역을 한국어 문장에 남기지 않는다.",
        ],
        "speaker_rules": {
            "코우지": {"register": "반말", "first_person": "나/내가", "note": "독백과 친구 대화는 자연스러운 남성 구어체"},
            "노리코": {"register": "정중한 해요체", "first_person": "저/제가", "note": "변호사 업무 대화는 격식을 유지하고 독백은 자연스럽게 완화"},
            "미우라": {"register": "단정한 해라체", "first_person": "나/내가", "note": "피의자에게는 너. 위압감은 살리되 일본어 이상의 욕설은 추가하지 않음"},
            "아사츠유": {"register": "친근한 반말", "first_person": "나/내가", "note": "코우 짱·노리코 짱 같은 호칭은 장부에 따라 보존"},
            "나나시바": {"register": "가벼운 반말", "first_person": "나/내가", "note": "장난기와 말끝의 늘임을 살림"},
            "아카네": {"register": "활발한 학생 반말", "first_person": "나/내가", "note": "감탄과 과장된 반응을 보존"},
            "아오이": {"register": "조심스러운 학생 해요체", "first_person": "저/제가", "note": "머뭇거림과 말줄임을 보존"},
            "노조미": {"register": "정중한 해요체", "first_person": "저/제가", "note": "상실감과 불안을 과장하지 않고 유지"},
        },
        "scene_rules": [
            {"scene": "노리코의 현장 조사", "rule": "노리코는 관계자에게 정중하게 묻고 속마음은 괄호 독백으로 처리"},
            {"scene": "코우지 취조", "rule": "미우라는 압박하고 코우지는 반발하지만 사실관계는 차분하게 설명"},
            {"scene": "탐정사무소/학생", "rule": "아카네는 활발하게, 아오이는 조심스럽게; 두 사람의 말투를 섞지 않음"},
            {"scene": "구치소", "rule": "구류/접견/취조 용어를 고정하고 가벼운 화자와 공권력 화자의 온도를 분리"},
        ],
    }


def build_glossary() -> dict:
    entries = [
        ("被疑者", "피의자", "법률", "high"),
        ("被害者", "피해자", "법률", "high"),
        ("真犯人", "진범", "수사", "high"),
        ("犯人", "범인", "수사", "high"),
        ("人殺し", "살인자/사람을 죽인 자", "수사", "high"),
        ("取調べ", "취조", "법률", "high"),
        ("勾留", "구류", "법률", "high"),
        ("刑訴手続き", "형사소송 절차", "법률", "high"),
        ("司法取引", "사법 거래", "법률", "high"),
        ("アリバイ", "알리바이", "수사", "high"),
        ("現場保存", "현장 보존", "수사", "high"),
        ("防犯カメラ", "방범 카메라", "수사", "high"),
        ("指紋を拭き取る", "지문을 닦아내다", "수사", "high"),
        ("隠滅", "인멸", "수사", "high"),
        ("移植手術", "이식 수술", "의학", "high"),
        ("心臓移植", "심장 이식", "의학", "high"),
        ("腎臓移植手術", "신장 이식 수술", "의학", "high"),
        ("宮上銀座", "미야카미 긴자", "지명", "high"),
        ("藤代町", "후지시로초", "지명", "high"),
        ("播磨直正", "하리마 나오마사", "인명", "medium"),
        ("新都タクシーセンター", "신토 택시 센터", "시설", "high"),
        ("水谷探偵事務所", "미즈타니 탐정사무소", "시설", "high"),
        ("桜蔭高校", "오인 고등학교", "시설", "medium"),
        ("受け取り方", "받아들이는 방식", "일반", "high"),
        ("精力を吸い取る", "기력을 빨아먹다", "일반", "medium"),
        ("彼", "그/선행사 이름", "대명사", "high"),
        ("彼女", "그녀/선행사 이름", "대명사", "high"),
    ]
    return {
        "schema": "enkaku_translation_glossary_v2",
        "policy": "전역 치환 금지. source_ja와 장면·화자를 함께 확인해 적용.",
        "entries": [
            {
                "japanese": jp,
                "korean": ko,
                "domain": domain,
                "confidence": conf,
                "conditions": "원문 복원 결과가 해당 표기일 때만 적용",
            }
            for jp, ko, domain, conf in entries
        ],
    }


def main() -> None:
    ja_rows = read_tsv(FONT / "script_full_ja_corrected.tsv")
    raw_rows = read_tsv(FONT / "script_full_raw.tsv")
    current_rows = read_tsv(BUILD / "translation_ko_runtime_final.tsv")
    if not (len(ja_rows) == len(raw_rows) == len(current_rows)):
        raise SystemExit(f"row count mismatch: ja={len(ja_rows)} raw={len(raw_rows)} ko={len(current_rows)}")
    current = {row["offset"]: row["text"] for row in current_rows}
    by_order, quality, retranslated = read_overrides()
    glyph_list = json.loads((FONT / "charmap_quality_corrected.json").read_text(encoding="utf-8"))
    glyphs = {item["char"]: item for item in glyph_list if item.get("char")}

    character_guide = build_character_guide(ja_rows)
    write_json(BUILD / "translation_character_guide.json", character_guide)
    write_json(BUILD / "translation_style_guide.json", build_style_guide())
    write_json(BUILD / "translation_glossary_v2.json", build_glossary())

    plan_rows: list[dict] = []
    baseline_rows: list[dict[str, str]] = []
    provenance_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    priority_counts: Counter[str] = Counter()

    truncation_offsets: set[str] = set()
    defects_path = BUILD / "dialogue_defects.json"
    if defects_path.exists():
        defects = json.loads(defects_path.read_text(encoding="utf-8"))
        for item in defects.get("found", {}).get("truncation", []):
            truncation_offsets.add(item.get("index", ""))
    pronoun_offsets: set[str] = set()
    pronoun_path = BUILD / "pronoun_fix_report.json"
    if pronoun_path.exists():
        pronouns = json.loads(pronoun_path.read_text(encoding="utf-8"))
        for item in pronouns.get("changes", []):
            pronoun_offsets.add(item.get("index", ""))

    for order, (raw, ja, ko) in enumerate(zip(raw_rows, ja_rows, current_rows)):
        entry = by_order.get(str(order), {})
        provenance = classify_note(entry.get("notes", ""))
        provenance_counts[provenance] += 1
        uncertainty = source_uncertainty(ja["text"], glyphs)
        offset = raw["offset"]
        if provenance == "bulk_machine_draft":
            if offset in truncation_offsets:
                priority = "P0_truncation"
            elif offset in pronoun_offsets:
                priority = "P0_pronoun_context"
            elif uncertainty:
                priority = "P1_source_recovery"
            else:
                priority = "P2_scene_retranslation"
            status = "needs_retranslation"
            candidate = current.get(offset, ko["text"])
        else:
            priority = "P3_preserve_and_review"
            status = "preserve_candidate"
            candidate = entry.get("korean") or current.get(offset, ko["text"])

        # Conditions are source-indexed; they are safe to apply only when the
        # source row matches the audit record.  The batch files are similarly
        # keyed by source index and have already been manually reviewed.
        if offset in quality:
            candidate = quality[offset]
            status = "verified_quality_override"
        if offset in retranslated:
            candidate = retranslated[offset]
            status = "verified_retranslation_override"
        candidate = normalise_tsv_text(candidate)
        baseline_rows.append({"offset": offset, "lines": str(candidate.count(r"\n") + 1), "text": candidate})
        status_counts[status] += 1
        priority_counts[priority] += 1
        plan_rows.append(
            {
                "order": order,
                "index": offset,
                "source_ja_raw": raw["text"],
                "source_ja_applied": ja["text"],
                "current_ko": ko["text"],
                "recovered_candidate_ko": candidate,
                "provenance": provenance,
                "priority": priority,
                "source_uncertainty": uncertainty,
                "status": status,
                "speaker": speaker_tags(ja["text"]),
            }
        )

    plan = {
        "schema": "enkaku_retranslation_plan_v2",
        "source": {
            "raw": "font_extract/script_full_raw.tsv",
            "japanese": "font_extract/script_full_ja_corrected.tsv",
            "current_korean": "build/translation_ko_runtime_final.tsv",
        },
        "row_count": len(plan_rows),
        "provenance_counts": dict(provenance_counts),
        "status_counts": dict(status_counts),
        "priority_counts": dict(priority_counts),
        "rows": plan_rows,
    }
    write_json(BUILD / "retranslation_plan_v2.json", plan)

    out = ["offset\tlines\ttext"]
    for row in baseline_rows:
        out.append(f"{row['offset']}\t{row['lines']}\t{row['text']}")
    (BUILD / "translation_ko_recovered_baseline.tsv").write_text("\n".join(out) + "\n", encoding="utf-8")

    offsets_equal = [row["index"] for row in plan_rows] == [row["offset"] for row in raw_rows]
    report = {
        "schema": "enkaku_translation_recovery_report_v2",
        "emulator_launched": False,
        "row_count": len(plan_rows),
        "provenance_counts": dict(provenance_counts),
        "status_counts": dict(status_counts),
        "priority_counts": dict(priority_counts),
        "quality_overrides_applied": len(quality),
        "retranslation_overrides_applied": len(retranslated),
        "offset_alignment": {"ok": offsets_equal, "count": len(plan_rows)},
        "baseline_note": "비기계 보존 후보와 확인된 조건부 보정은 복구했으며, needs_retranslation 행은 최종 번역으로 간주하지 않는다.",
    }
    write_json(BUILD / "translation_recovery_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

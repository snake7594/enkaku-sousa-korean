"""Build a Claude-Code-ready translation context from the extracted script.

This is a derived artifact generator.  It intentionally keeps both the exact
indexed source and the current best-effort Japanese rendering: the latter is
convenient for translation, while the former prevents uncertain glyph
assignments from being silently treated as facts.
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "font_extract"
OUT = FONT_DIR / "translation_context_for_claude.json"
OVERRIDES = FONT_DIR / "translation_overrides.json"
ADDITIONAL_CONFIRMATIONS = FONT_DIR / "charmap_additional_confirmed.json"
INDEX_RE = re.compile(r"\[(\d+)\]")


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def classify(text: str) -> str:
    if text.startswith("【"):
        return "dialogue"
    if text.startswith(("［", "<", "␛")):
        return "ui_or_control"
    return "narration_or_system"


def main() -> None:
    charmap = json.loads((FONT_DIR / "charmap_final.json").read_text(encoding="utf-8"))
    by_index = {int(item["index"]): item for item in charmap}
    charmap_indices = set(by_index)
    # Keep charmap_final immutable, but treat the separately audited ledger as
    # authoritative for this Claude-facing derived artifact.  This prevents
    # already-confirmed glyphs from continuing to appear in every review list.
    additional_confirmed: dict[int, str] = {}
    additional_data: dict[str, object] = {}
    if ADDITIONAL_CONFIRMATIONS.exists():
        additional = json.loads(ADDITIONAL_CONFIRMATIONS.read_text(encoding="utf-8"))
        additional_data = additional
        for item in additional.get("character_confirmations", []):
            indices = item.get("glyph_indices", [])
            confirmed = item.get("confirmed", "")
            if len(indices) != len(confirmed):
                continue
            for index, char in zip(indices, confirmed):
                additional_confirmed[int(index)] = char
        # Phrase confirmations remain contextual evidence.  They are applied
        # to exact phrases by rebuild_script_ja_with_confirmations.py, but are
        # deliberately not promoted to a global per-glyph mapping because a
        # code point can be reused in a different word (e.g. [280]).
        for index, char in additional_confirmed.items():
            if index in by_index:
                by_index[index] = {
                    **by_index[index],
                    "char": char,
                    "confidence": "high",
                    "source": "additional_context_confirmed",
                }
    overrides = {"by_order": {}, "by_japanese_applied": {}}
    if OVERRIDES.exists():
        overrides = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    by_order = {str(key): value for key, value in overrides.get("by_order", {}).items()}
    by_text = overrides.get("by_japanese_applied", {})
    raw_rows = read_tsv(FONT_DIR / "script_full_raw.tsv")
    ja_rows = read_tsv(FONT_DIR / "script_full_ja.tsv")
    if len(raw_rows) != len(ja_rows):
        raise RuntimeError(f"row count mismatch: raw={len(raw_rows)} ja={len(ja_rows)}")

    refs: dict[int, list[dict[str, str]]] = defaultdict(list)
    entries: list[dict[str, object]] = []
    unresolved_counts = defaultdict(int)

    for order, (raw, ja) in enumerate(zip(raw_rows, ja_rows)):
        if raw["offset"] != ja["offset"]:
            raise RuntimeError(f"offset mismatch at row {order}: {raw['offset']} != {ja['offset']}")
        indices = [int(x) for x in INDEX_RE.findall(raw["text"])]
        review: list[dict[str, object]] = []
        seen: set[int] = set()
        for index in indices:
            if index in seen:
                continue
            seen.add(index)
            item = by_index.get(index)
            if item is None:
                # Extended slots 1368+ are recorded in the separate
                # confirmation ledger when their meaning is established from
                # ruby/context.  They are not part of the original 0~1367
                # charmap, but confirmed extensions should not keep every
                # translated row in a false "needs review" state.
                if index in additional_confirmed:
                    continue
                review.append({"index": index, "status": "missing_from_charmap"})
                continue
            if item.get("confidence") == "high":
                continue
            unresolved_counts[index] += 1
            review_item = {
                "index": index,
                "current_char": item.get("char"),
                "confidence": item.get("confidence"),
                "source": item.get("source"),
                "uses": item.get("uses"),
                "alternatives": item.get("alts", []),
            }
            review.append(review_item)
            refs[index].append({
                "offset": raw["offset"],
                "order": order,
                "text": ja["text"],
            })

        entry = {
            "order": order,
            "offset": raw["offset"],
            "display_lines": int(raw["lines"]),
            "kind": classify(ja["text"]),
            "source": {
                "raw_indexed": raw["text"],
                "japanese_applied": ja["text"],
                "glyph_indices": indices,
            },
            "translation": {
                "korean": None,
                "status": "pending",
                "review_required": bool(review),
            },
            "kanji_review": review,
        }

        override = by_order.get(str(order)) or by_text.get(ja["text"])
        if override:
            if isinstance(override, str):
                override = {"korean": override}
            korean = override.get("korean")
            if korean is not None:
                entry["translation"]["korean"] = korean
                entry["translation"]["status"] = "translated"
            if override.get("notes"):
                entry["translation"]["notes"] = override["notes"]
            if override.get("japanese_reviewed"):
                entry["source"]["japanese_reviewed"] = override["japanese_reviewed"]
        entries.append(entry)

    unresolved = []
    for item in by_index.values():
        if item.get("confidence") == "high":
            continue
        index = int(item["index"])
        contexts = refs.get(index, [])
        unresolved.append({
            "index": index,
            "current_char": item.get("char"),
            "confidence": item.get("confidence"),
            "source": item.get("source"),
            "uses_in_charmap": item.get("uses"),
            "uses_in_script_rows": unresolved_counts.get(index, 0),
            "alternatives": item.get("alts", []),
            "contexts": contexts[:20],
            "context_count": len(contexts),
            "status": "resolve_from_context_before_final_translation",
        })

    translated_count = sum(entry["translation"]["korean"] is not None for entry in entries)
    out_of_range_counts: defaultdict[int, int] = defaultdict(int)
    for row in raw_rows:
        for raw_index in INDEX_RE.findall(row["text"]):
            index = int(raw_index)
            if index not in charmap_indices:
                out_of_range_counts[index] += 1
    out_of_range_indices = sorted(out_of_range_counts)
    out_of_range_confirmed = [index for index in out_of_range_indices if index in additional_confirmed]
    out_of_range_unconfirmed = [index for index in out_of_range_indices if index not in additional_confirmed]
    data = {
        "schema": "enkaku-sousa-translation-context/v1",
        "purpose": "Faithful Japanese-to-Korean translation context for Claude Code.",
        "generated_from": {
            "raw_script": "font_extract/script_full_raw.tsv",
            "japanese_script": "font_extract/script_full_ja.tsv",
            "charmap": "font_extract/charmap_final.json",
            "charmap_tsv": "font_extract/charmap_final.tsv",
            "additional_charmap_confirmations": "font_extract/charmap_additional_confirmed.json",
        },
        "translation_policy": {
            "language": "ko-KR",
            "instruction": "Translate faithfully from the Japanese meaning and context. Do not omit, sanitize, or paraphrase away evidence-related details.",
            "source_priority": [
                "source.raw_indexed plus charmap context",
                "source.japanese_applied",
                "local dialogue context",
            ],
            "uncertain_kanji": "Resolve medium/low-confidence glyphs from surrounding Japanese, ruby readings, speaker context, and recurring terminology before committing the Korean translation.",
            "format": "Keep offsets and entry order unchanged. Preserve literal \\n escapes, speaker brackets 【...】, UI brackets ［...］, ruby brackets 《...》, and control tags such as <8100> unless a separate patching pass explicitly changes them.",
            "names": "Keep character and place names consistent across entries; record a name decision in translation.notes when needed.",
        },
        "translation_glossary": {
            "新城法子／法子": "신조 노리코／노리코",
            "斉藤光志／斎藤光志／光志／コウジ": "사이토 코우지／코우지",
            "水無月幸司／水無月": "미나즈키 코우지／미나즈키",
            "白川一朗": "시라카와 이치로",
            "白川真二": "시라카와 신지",
            "白川悟／白側悟": "시라카와 사토루",
            "三浦正信／礼吉": "미우라 마사노부／미우라",
            "沼崎慎太郎／教授震多樓": "누마사키 신타로／신타로",
            "沼崎法律事務所／教授法律事務所": "누마사키 법률사무소",
            "吉本／義本": "요시모토",
            "七芝伊月／斜縛": "나나시바 이츠키／나나시바",
            "留置係／竜蟠勁": "구치소 직원",
            "留置場／竜蟠場": "구치소",
            "白川真二／真鰺": "시라카와 신지／신지",
            "樋口": "히구치",
            "近藤": "콘도",
            "所長／所場": "소장／소장님",
            "廊下／珍貨": "복도",
            "非常口／非紕口": "비상구",
            "管理人室／疫痢人室": "관리인실",
            "中川理恵／中側痢恵／中吟醸": "나카가와 리에／나카가와",
            "テーブル上／テーブル龍": "테이블 위",
            "白川": "시라카와",
            "美佐恵／ミサエ": "미사에",
            "のぞみ": "노조미",
            "東条": "토죠",
            "中側": "나카가와",
            "水谷朝露": "미즈타니 아사츠유",
            "水無月葵": "미나즈키 아오이",
            "三浦正信": "미우라 마사노부",
            "吉本ユミ": "요시모토 유미",
            "朝露": "아사츠유",
            "葵": "아오이",
            "ドアフォン": "도어폰",
            "ヘルパー": "가사도우미",
            "受付嬢": "접수원",
            "加瀬教授": "가세 교수",
            "探偵倶楽部": "탐정 동아리",
            "免疫抑制剤": "면역억제제",
            "患者名簿": "환자 명부",
            "虚血性腸炎": "허혈성 장염",
            "警察上層部": "경찰 상층부",
            "豊島": "도요시마(시각 확인 전 후보)",
        },
        "font_reference": {
            "standard_pgf": False,
            "primary_glyph_source": {
                "iso_file": "/PSP_GAME/USRDIR/0000",
                "stream_offset": "0x27e000",
                "resource_id": "0x80",
                "format": "16x16 4bpp glyphs",
                "tile_layout": "32x16 tile containing two glyphs",
                "extracted_preview": "font_extract/enkaku_font.png",
                "extracted_binary": "font_extract/enkaku_font.bin",
            },
            "kana_source": {
                "iso_file": "/PSP_GAME/SYSDIR/BOOT.BIN",
                "offset": "0x92060",
                "note": "Kana glyph table identified during the font analysis.",
            },
        },
        "stats": {
            "entry_count": len(entries),
            "display_line_count": sum(int(row["lines"]) for row in raw_rows),
            "unresolved_charmap_count": len(unresolved),
            "out_of_range_glyph_count": len(out_of_range_indices),
            "out_of_range_confirmed_count": len(out_of_range_confirmed),
            "out_of_range_unconfirmed_count": len(out_of_range_unconfirmed),
            "out_of_range_script_occurrences": sum(out_of_range_counts.values()),
            "out_of_range_unconfirmed_script_occurrences": sum(out_of_range_counts[index] for index in out_of_range_unconfirmed),
            "entries_requiring_kanji_review": sum(bool(entry["kanji_review"]) for entry in entries),
            "translation_completed": translated_count,
            "translation_percent": round(translated_count * 100 / len(entries), 2) if entries else 0,
            "translation_pending": len(entries) - translated_count,
        },
        "unresolved_kanji": unresolved,
        "additional_kanji_confirmations": additional_data,
        "entries": entries,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print(json.dumps(data["stats"], ensure_ascii=False))


if __name__ == "__main__":
    main()

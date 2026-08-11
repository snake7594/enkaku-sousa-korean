"""Verify the stable expanded build without launching PPSSPP."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))

import build_patch  # noqa: E402
import build_runtime_refs  # noqa: E402
import iso9660  # noqa: E402
import lzss  # noqa: E402
import ref_manifest  # noqa: E402
import reflow  # noqa: E402
import text_blocks  # noqa: E402
import translation_text  # noqa: E402


BASE_ISO = ROOT / "build" / "Enkaku_Korean_RUNTIME_CFG17_SEMANTIC_REVIEW.iso"
ISO = ROOT / "build" / "Enkaku_Korean_CFG18_STABLE.iso"
ARCHIVE_EXPECTED = ROOT / "build" / "0000_cfg18_stable.bin"
ORIGINAL_STREAM = ROOT / "font_extract" / "script_stream.bin"
BASE_STREAM = ROOT / "build" / "stream1_ko_font_clean.bin"
FINAL_STREAM = ROOT / "build" / "stream1_ko_runtime_cfg18_stable.bin"
TSV = ROOT / "build" / "translation_ko_runtime_final.tsv"
SLOTS = ROOT / "build" / "korean_slots_full_clean.json"
CORRECTIONS = ROOT / "build" / "runtime_reference_supplement_cfg17.json"
RUNTIME_REPORT = ROOT / "build" / "runtime_cfg18_stable_report.json"
OUTPUT = ROOT / "build" / "verify_cfg18_stable.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file_outside(path: Path, skip_start: int, skip_end: int) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        remaining = skip_start
        while remaining:
            chunk = stream.read(min(8 * 1024 * 1024, remaining))
            if not chunk:
                raise ValueError(f"unexpected EOF before skipped region in {path}")
            digest.update(chunk)
            remaining -= len(chunk)
        stream.seek(skip_end)
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    base = BASE_STREAM.read_bytes()
    original = ORIGINAL_STREAM.read_bytes()
    final_stream = FINAL_STREAM.read_bytes()
    expected_archive = ARCHIVE_EXPECTED.read_bytes()
    iso = ISO.read_bytes()

    slots = {
        char: int(index)
        for char, index in json.loads(SLOTS.read_text(encoding="utf-8"))["slots"].items()
    }
    spans, texts, text_stats = build_patch.build_spans(
        base, TSV, slots, apply_overrides=False
    )
    rebuilt_without_refs, mapping = reflow.rebuild(base, spans, texts)

    record = iso9660.find_record(iso, "/PSP_GAME/USRDIR/0000")
    archive_start = record.extent * 2048
    archive_end = archive_start + record.size
    archive = iso[archive_start:archive_end]
    extracted_stream, packed_size = lzss.decompress(archive, 0x27E000)

    text_mismatches = []
    for span, text in zip(spans, texts):
        start = mapping[span.text]
        if extracted_stream[start:start + len(text)] != text:
            text_mismatches.append(
                {"source_offset": span.text, "mapped_offset": start}
            )
            if len(text_mismatches) >= 16:
                break

    translated_spans, _translated_texts, _ = build_patch.build_spans(
        original, TSV, slots, apply_overrides=False
    )
    blocks = text_blocks.find_blocks(original)
    flags = ref_manifest.membership(original, blocks)
    for span in translated_spans:
        flags[span.text:span.text_end] = b"\x01" * (span.text_end - span.text)
    build_runtime_refs.extend_runtime_opaque_flags(
        flags,
        build_runtime_refs.runtime_marker_ends(original, blocks),
        blocks,
    )
    runtime_refs, collect_stats, cfg_records = build_runtime_refs.collect_runtime_refs(
        original, flags
    )
    typed_refs = build_runtime_refs.collect_typed_pointer_refs(
        original, flags, cfg_records
    )
    supplemental, excluded, correction_stats = (
        build_runtime_refs.load_reference_corrections(CORRECTIONS)
    )
    refs, ref_stats = build_runtime_refs.load_all_refs(
        runtime_refs + typed_refs,
        original,
        flags,
        cfg_records,
        supplemental,
        excluded,
    )
    reference_mismatches = []
    for address, value in refs:
        mapped_address = mapping[address]
        actual = int.from_bytes(
            extracted_stream[mapped_address:mapped_address + 4], "little"
        )
        expected = mapping[value]
        if actual != expected:
            reference_mismatches.append(
                {
                    "source_address": address,
                    "source_value": value,
                    "actual": actual,
                    "expected": expected,
                }
            )
            if len(reference_mismatches) >= 16:
                break

    _, translation_rows = translation_text.parse_loose_tsv(TSV)
    residual_rows = []
    story_over_width = []
    all_over_width = []
    for offset, _line_count, text in translation_rows:
        if translation_text.RESIDUAL_RE.search(text.replace(r"\n", "")):
            residual_rows.append(offset)
        story = translation_text.is_story_text(
            text, include_fullwidth_choices=True
        )
        for line_number, line in enumerate(
            text.replace(r"\n", "\n").split("\n"), 1
        ):
            if len(line) > translation_text.DEFAULT_MAX_DIALOGUE_WIDTH:
                item = {
                    "offset": offset,
                    "line": line_number,
                    "characters": len(line),
                    "text": line,
                }
                all_over_width.append(item)
                if story:
                    story_over_width.append(item)

    outside_final_hash = hash_file_outside(ISO, archive_start, archive_end)
    outside_base_hash = hash_file_outside(BASE_ISO, archive_start, archive_end)
    correction_payload = json.loads(CORRECTIONS.read_text(encoding="utf-8"))
    runtime_payload = json.loads(RUNTIME_REPORT.read_text(encoding="utf-8"))

    checks = {
        "iso_size_matches_cfg17": ISO.stat().st_size == BASE_ISO.stat().st_size,
        "iso_outside_archive_matches_cfg17": outside_final_hash == outside_base_hash,
        "archive_matches_rebuilt": archive == expected_archive,
        "stream_matches_expected": extracted_stream == final_stream,
        "stream_size_matches_reflow": len(extracted_stream) == len(rebuilt_without_refs),
        "all_text_matches": not text_mismatches,
        "all_references_match": not reference_mismatches,
        "all_rows_encodable": text_stats["failed"] == 0,
        "no_overlapping_text_spans": text_stats["overlap"] == 0,
        "no_foreign_characters": not residual_rows,
        "no_story_lines_over_width": not story_over_width,
        "cfg17_reference_model_reproduced_exactly": correction_payload[
            "verification"
        ]["reproduces_working_stream_exactly"],
        "runtime_report_has_no_ref_conflicts": not runtime_payload[
            "references"
        ]["duplicate_or_conflicting_runtime_refs"],
    }
    report = {
        "schema": "enkaku-cfg18-stable-verification-v1",
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "iso": {
            "path": str(ISO),
            "size": len(iso),
            "sha256": sha256(iso),
            "base": str(BASE_ISO),
            "archive_lba": record.extent,
            "archive_size": record.size,
            "outside_archive_sha256": outside_final_hash,
        },
        "archive": {
            "sha256": sha256(archive),
            "packed_stream1_size": packed_size,
        },
        "stream": {
            "path": str(FINAL_STREAM),
            "size": len(final_stream),
            "sha256": sha256(final_stream),
            "detectable_blocks": len(text_blocks.find_blocks(final_stream)),
        },
        "translation": {
            "path": str(TSV),
            "rows": text_stats["rows"],
            "usable_spans": len(spans),
            "encoding_failures": text_stats["failed"],
            "overlaps": text_stats["overlap"],
            "text_mismatches": text_mismatches,
            "foreign_character_rows": residual_rows,
            "story_lines_over_19": story_over_width,
            "all_lines_over_19_count": len(all_over_width),
            "all_lines_over_19_sample": all_over_width[:20],
        },
        "references": {
            "total": len(refs),
            "selected_runtime_refs": collect_stats["selected_runtime_refs"],
            "typed_pointer_refs": len(typed_refs),
            "supplemental_refs": len(supplemental),
            "excluded_false_refs": len(excluded),
            "mismatches": reference_mismatches,
            "stats": ref_stats,
            "correction_stats": correction_stats,
        },
        "emulator_launched": False,
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT),
                "status": report["status"],
                "iso_sha256": report["iso"]["sha256"],
                "archive_lba": record.extent,
                "text_rows": text_stats["rows"],
                "text_mismatches": len(text_mismatches),
                "reference_count": len(refs),
                "reference_mismatches": len(reference_mismatches),
                "story_lines_over_19": len(story_over_width),
                "emulator_launched": False,
            },
            ensure_ascii=True,
        )
    )
    if report["status"] != "pass":
        raise SystemExit("CFG18 verification failed")


if __name__ == "__main__":
    main()

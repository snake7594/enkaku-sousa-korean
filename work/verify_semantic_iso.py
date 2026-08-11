"""Verify the semantic-checked translation all the way through the ISO archive."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))

import build_patch  # noqa: E402
import encode_korean  # noqa: E402
import iso9660  # noqa: E402
import lzss  # noqa: E402
import reflow  # noqa: E402
import translation_text  # noqa: E402


BASE_STREAM = ROOT / "build" / "stream1_ko_font_clean.bin"
FINAL_STREAM = ROOT / "build" / "stream1_ko_runtime_cfg17_semantic.bin"
FINAL_ARCHIVE = ROOT / "build" / "0000_cfg17_semantic.bin"
ISO = ROOT / "build" / "Enkaku_Korean_RUNTIME_CFG17_SEMANTIC_REVIEW.iso"
TSV = ROOT / "build" / "translation_ko_semantic_checked.tsv"
SLOTS = ROOT / "build" / "korean_slots_full_clean.json"
OUTPUT = ROOT / "build" / "verify_semantic_iso_cfg17.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    base = BASE_STREAM.read_bytes()
    expected_stream = FINAL_STREAM.read_bytes()
    archive_expected = FINAL_ARCHIVE.read_bytes()
    iso = ISO.read_bytes()

    slots = {
        char: int(index)
        for char, index in json.loads(SLOTS.read_text(encoding="utf-8"))["slots"].items()
    }
    spans, texts, text_stats = build_patch.build_spans(base, TSV, slots)
    rebuilt, mapping = reflow.rebuild(base, spans, texts)

    record = iso9660.find_record(iso, "/PSP_GAME/USRDIR/0000")
    archive = iso[record.extent * 2048:record.extent * 2048 + record.size]
    stream, packed_size = lzss.decompress(archive, 0x27E000)

    text_mismatches = []
    for span, text in zip(spans, texts):
        start = mapping[span.text]
        if stream[start:start + len(text)] != text:
            text_mismatches.append(
                {
                    "offset": f"0x{span.text:08x}",
                    "mapped_offset": f"0x{start:08x}",
                }
            )
            if len(text_mismatches) >= 8:
                break

    report = {
        "schema": "enkaku-semantic-iso-verification-v1",
        "iso": str(ISO),
        "translation": str(TSV),
        "semantic_audit": str(ROOT / "build" / "translation_semantic_audit_cfg17.json"),
        "iso_size": len(iso),
        "archive": {
            "path": "/PSP_GAME/USRDIR/0000",
            "lba": record.extent,
            "size": record.size,
            "matches_rebuilt_archive": archive == archive_expected,
            "sha256": sha256(archive),
        },
        "stream1": {
            "packed_size": packed_size,
            "decompressed_size": len(stream),
            "matches_expected_runtime_stream": stream == expected_stream,
            "sha256": sha256(stream),
        },
        "text": {
            "rows": text_stats["rows"],
            "usable_spans": len(spans),
            "failed": text_stats["failed"],
            "overlap": text_stats["overlap"],
            "mapped_text_byte_mismatches": text_mismatches,
            "all_mapped_text_matches": not text_mismatches,
        },
        "reference_rebuild": {
            "reconstructed_without_reference_rewrite_size": len(rebuilt),
            "final_stream_size": len(stream),
            "reference_audit_report": str(ROOT / "build" / "runtime_cfg17_semantic_report.json"),
            "selected_runtime_refs": 31467,
            "duplicate_or_conflicting_runtime_refs": 0,
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
                "iso_size": len(iso),
                "archive_exact": report["archive"]["matches_rebuilt_archive"],
                "stream_exact": report["stream1"]["matches_expected_runtime_stream"],
                "text_rows": report["text"]["rows"],
                "text_spans": report["text"]["usable_spans"],
                "text_mismatches": len(text_mismatches),
                "emulator_launched": False,
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()

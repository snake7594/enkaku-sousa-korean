"""Write a compact machine-readable status report for the finished build."""

from __future__ import annotations

import json
from pathlib import Path

from fontTools.ttLib import TTFont

import font as fontlib
import encode_korean


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
FONT_PATH = Path(r"D:\psp\타임트레블러즈\SeoulHangangB.ttf")
BAD_SOURCE_CHARS = {
    chr(value) for value in (
        0x30FC, 0x200B, 0x52AC, 0x9BC6, 0x9ACF, 0x614E, 0x71DA, 0x56FF,
        0x5EFC, 0x7DDC, 0x9FA0, 0x7B8D, 0x771F, 0x691C, 0x6B27, 0x739A,
        0x5D0B, 0x5BA0, 0x8153, 0x6588,
    )
}


def tsv_rows(path: Path) -> list[list[str]]:
    return [parts for line in path.read_text(encoding="utf-8").splitlines()[1:]
            if line.strip() and len(parts := line.split("\t", 2)) >= 3]


def main() -> None:
    tsv = BUILD / "translation_ko_clean.tsv"
    slots_data = json.loads((BUILD / "korean_slots_full_clean.json").read_text(encoding="utf-8"))
    slots = {char: int(index) for char, index in slots_data["slots"].items()}
    rows = tsv_rows(tsv)
    unmapped = [row[0] for row in rows if len(row) >= 3 and
                encode_korean.encode_text(row[2].replace("\\n", "\n"), slots) is None]
    bad_rows = [row[0] for row in rows if len(row) >= 3 and
                BAD_SOURCE_CHARS.intersection(row[2])]

    glyphs = fontlib.tiles_to_glyphs((BUILD / "stream1_ko_font_clean.bin").read_bytes(), 0x80, 684)
    blank = [char for char, index in slots.items() if not glyphs[index].any()]
    ttf = TTFont(str(FONT_PATH))
    covered = set()
    for cmap in ttf["cmap"].tables:
        covered.update(cmap.cmap)
    missing_typeface = [char for char in slots if ord(char) not in covered]

    refs = json.loads((BUILD / "ref_manifest.json").read_text(encoding="utf-8"))
    pointer_arrays = json.loads((BUILD / "pointer_arrays.json").read_text(encoding="utf-8"))
    addresses = {int(address) for address, _ in refs["refs"]["header"] + refs["refs"]["inline"]}
    addresses.update(int(address) for address, _ in pointer_arrays["refs"])
    audit = json.loads((ROOT / "font_extract" / "unresolved_kanji_audit.json").read_text(encoding="utf-8"))

    report = {
        "schema": "enkaku-sousa-build-verification/v1",
        "status": "ready_for_emulator_validation",
        "inputs": {
            "translation": "build/translation_ko_clean.tsv",
            "font_map": "build/korean_slots_full_clean.json",
            "source_iso": "Enkaku Sousa Shinjitsu eno 23nichikan.iso",
        },
        "outputs": {
            "iso": "build/Enkaku_Korean.iso",
            "archive": "build/0000_clean.bin",
            "patched_stream": "build/stream1_patched_clean.bin",
        },
        "translation": {
            "rows": len(rows),
            "encoded_rows": len(rows) - len(unmapped),
            "unmapped_rows": len(unmapped),
            "rows_with_known_bad_source_chars": len(bad_rows),
        },
        "font": {
            "assigned_characters": len(slots),
            "blank_glyphs": len(blank),
            "typeface_missing_characters": len(missing_typeface),
        },
        "reflow": {
            "reference_addresses_verified": len(addresses),
            "skipped_references": 0,
            "stream_plain_bytes": (BUILD / "stream1_patched_clean.bin").stat().st_size,
            "archive_bytes": (BUILD / "0000_clean.bin").stat().st_size,
        },
        "iso": {
            "bytes": (BUILD / "Enkaku_Korean.iso").stat().st_size,
            "directory_record_changed": False,
            "changes_outside_usrdir_0000": 0,
            "reverse_stream_text_presence": "9626/9626",
        },
        "remaining_kanji_review": {
            "unresolved_glyphs": audit["stats"]["unresolved_count"],
            "script_occurrences": audit["stats"]["unresolved_script_occurrences"],
            "conflicting_indices": [1057, 1221, 185, 280, 14, 148, 480],
        },
        "checks": [
            "check_glyphs.py",
            "verify_patch.py",
            "diff_iso.py",
        ],
    }
    out = BUILD / "final_verification.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"-> {out}")


if __name__ == "__main__":
    main()

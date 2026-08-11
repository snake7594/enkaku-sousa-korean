"""Recover references lost when Claude's manifest replaced the CFG17 manifest.

The user-tested CFG17 stream and a stream rebuilt from the same Korean text with the
current manifest differ only where the newer manifest failed to rewrite a reference.
Because both streams use the same text-growth map, each missing source reference can
be recovered without guessing:

* the current candidate still contains the original four-byte value;
* the tested CFG17 stream contains that value remapped through the growth map; and
* applying every recovered word to the current candidate must reproduce CFG17 exactly.

The resulting source-address/value pairs are independent of the Korean translation and
can therefore supplement future reflows.  This tool never launches the emulator.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))

import build_patch  # noqa: E402
import reflow  # noqa: E402


BASE = ROOT / "build" / "stream1_ko_font_clean.bin"
WORKING = ROOT / "build" / "stream1_ko_runtime_cfg17_semantic.bin"
CURRENT = ROOT / "build" / "diagnostic_semantic_current_manifest.bin"
TSV = ROOT / "build" / "translation_ko_semantic_checked.tsv"
SLOTS = ROOT / "build" / "korean_slots_full_clean.json"
OUTPUT = ROOT / "build" / "runtime_reference_supplement_cfg17.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    base = BASE.read_bytes()
    working = WORKING.read_bytes()
    current = CURRENT.read_bytes()
    if len(working) != len(current):
        raise SystemExit(
            f"candidate sizes differ: working={len(working)} current={len(current)}"
        )

    slots = {
        char: int(index)
        for char, index in json.loads(SLOTS.read_text(encoding="utf-8"))["slots"].items()
    }
    spans, texts, stats = build_patch.build_spans(base, TSV, slots)
    rebuilt, mapping = reflow.rebuild(base, spans, texts)
    if len(rebuilt) != len(working):
        raise SystemExit(
            f"growth-map size does not match CFG17: {len(rebuilt)} != {len(working)}"
        )

    text_bytes = bytearray(len(base))
    for span in spans:
        text_bytes[span.text : span.text_end] = b"\x01" * (span.text_end - span.text)

    differing = {index for index, pair in enumerate(zip(working, current)) if pair[0] != pair[1]}
    candidates: list[tuple[int, int, int, int]] = []
    exclusions: list[tuple[int, int, int, int]] = []
    for address in range(0, len(base) - 3):
        if any(text_bytes[address : address + 4]):
            continue
        mapped_address = mapping[address]
        if any(mapping[address + step] != mapped_address + step for step in range(1, 4)):
            continue
        original_word = base[address : address + 4]
        value = int.from_bytes(original_word, "little")
        if not (0 <= value <= len(base)):
            continue
        mapped_value = mapping[value]
        expected = mapped_value.to_bytes(4, "little")
        current_word = current[mapped_address : mapped_address + 4]
        working_word = working[mapped_address : mapped_address + 4]
        explained = sum(
            mapped_address + step in differing
            for step in range(4)
        )
        if not explained:
            continue
        if current_word == original_word and working_word == expected:
            candidates.append((address, value, mapped_address, mapped_value))
        elif current_word == expected and working_word == original_word:
            exclusions.append((address, value, mapped_address, mapped_value))

    candidates.sort()
    exclusions.sort()
    source_overlaps = [
        [candidates[index - 1][0], candidates[index][0]]
        for index in range(1, len(candidates))
        if candidates[index][0] < candidates[index - 1][0] + 4
    ]
    if source_overlaps:
        raise SystemExit(f"ambiguous overlapping recovered references: {source_overlaps[:8]}")

    reproduced = bytearray(current)
    for _address, _value, mapped_address, mapped_value in candidates:
        reproduced[mapped_address : mapped_address + 4] = mapped_value.to_bytes(4, "little")
    for address, _value, mapped_address, _mapped_value in exclusions:
        reproduced[mapped_address : mapped_address + 4] = base[address : address + 4]
    remaining = [
        index
        for index, pair in enumerate(zip(working, reproduced))
        if pair[0] != pair[1]
    ]
    if remaining:
        raise SystemExit(
            "recovered references do not reproduce CFG17; first remaining offsets: "
            + ", ".join(f"0x{offset:x}" for offset in remaining[:16])
        )

    report = {
        "schema": "enkaku-runtime-reference-supplement-v1",
        "basis": "user-tested CFG17 stream versus same-text current-manifest rebuild",
        "source_stream": str(BASE),
        "working_stream": str(WORKING),
        "current_manifest_stream": str(CURRENT),
        "translation": str(TSV),
        "source_ref_count": len(candidates),
        "refs": [[address, value] for address, value, _, _ in candidates],
        "exclude_ref_count": len(exclusions),
        "exclude_addresses": [address for address, _, _, _ in exclusions],
        "excluded_refs": [[address, value] for address, value, _, _ in exclusions],
        "verification": {
            "translation_rows": stats["rows"],
            "initial_differing_bytes": len(differing),
            "remaining_differing_bytes_after_apply": len(remaining),
            "reproduces_working_stream_exactly": not remaining,
            "working_sha256": sha256(working),
            "reproduced_sha256": sha256(bytes(reproduced)),
            "emulator_launched": False,
        },
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT),
                "source_ref_count": len(candidates),
                "exclude_ref_count": len(exclusions),
                "initial_differing_bytes": len(differing),
                "remaining_differing_bytes": len(remaining),
                "exact": not remaining,
                "emulator_launched": False,
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()

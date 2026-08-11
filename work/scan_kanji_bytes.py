"""Scan extracted game files for the two-byte codes of unresolved glyph slots.

This is a read-only cross-check: it does not alter the ISO or extracted data.
The report is useful for separating genuinely unused font slots from characters
that occur in menu/event data outside the main decoded script stream.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def code_for(index: int) -> bytes:
    return bytes((0x88 + index // 256, index % 256))


def scan_file(path: Path, patterns: dict[bytes, int], rx: re.Pattern[bytes], max_samples: int):
    counts: Counter[int] = Counter()
    samples: defaultdict[int, list[dict[str, object]]] = defaultdict(list)
    chunk_size = 8 * 1024 * 1024
    overlap = 1
    with path.open("rb") as fh:
        base = 0
        carry = b""
        while True:
            block = fh.read(chunk_size)
            if not block:
                break
            data = carry + block
            data_base = base - len(carry)
            for match in rx.finditer(data):
                index = patterns[match.group(0)]
                absolute = data_base + match.start()
                counts[index] += 1
                if len(samples[index]) < max_samples:
                    left = max(0, match.start() - 24)
                    right = min(len(data), match.end() + 24)
                    samples[index].append(
                        {
                            "offset": absolute,
                            "hex_window": data[left:right].hex(" "),
                        }
                    )
            base += len(block)
            carry = data[-overlap:]
    return counts, samples


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("indices", nargs="+", type=int)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--sample-limit", type=int, default=8)
    args = parser.parse_args()

    patterns = {code_for(i): i for i in args.indices}
    rx = re.compile(b"(?:" + b"|".join(re.escape(x) for x in patterns) + b")")
    roots = [ROOT / "iso_extract", ROOT / "font_extract" / "script_stream.bin"]
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(p for p in root.rglob("*") if p.is_file())

    report: dict[str, object] = {
        "schema": "enkaku-sousa-kanji-byte-scan/v1",
        "purpose": "미확정 글리프 코드가 메인 스크립트 밖의 게임 데이터에도 존재하는지 확인",
        "indices": args.indices,
        "byte_codes": {str(i): code_for(i).hex(" ") for i in args.indices},
        "files_scanned": len(files),
        "matches_by_index": {str(i): 0 for i in args.indices},
        "files_by_index": {str(i): {} for i in args.indices},
        "samples": {str(i): [] for i in args.indices},
        "script_text_span_matches_by_index": {str(i): 0 for i in args.indices},
        "script_text_span_offsets": {str(i): [] for i in args.indices},
    }

    total = Counter()
    for path in files:
        counts, samples = scan_file(path, patterns, rx, args.sample_limit)
        for index, count in counts.items():
            total[index] += count
            key = str(index)
            report["files_by_index"][key][str(path.relative_to(ROOT))] = count
            report["samples"][key].extend(
                {"file": str(path.relative_to(ROOT)), **sample} for sample in samples[index]
            )

    report["matches_by_index"] = {str(i): total[i] for i in args.indices}
    stream = ROOT / "font_extract" / "script_stream.bin"
    if stream.exists():
        # Raw byte matches elsewhere in the ISO are mostly compressed-data
        # coincidences.  Restrict this second pass to actual decoded text
        # spans, which is the meaningful test for unused script glyphs.
        import sys

        sys.path.insert(0, str(ROOT / "work"))
        from decode_script import text_spans

        stream_bytes = stream.read_bytes()
        for offset, span in text_spans(stream_bytes):
            for pattern, index in patterns.items():
                count = span.count(pattern)
                if count:
                    key = str(index)
                    report["script_text_span_matches_by_index"][key] += count
                    if len(report["script_text_span_offsets"][key]) < args.sample_limit:
                        report["script_text_span_offsets"][key].append(offset + span.find(pattern))
    report["samples"] = {
        str(i): report["samples"][str(i)][: args.sample_limit] for i in args.indices
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"scanned {len(files)} files")
    print(json.dumps(report["matches_by_index"], ensure_ascii=False, sort_keys=True))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()

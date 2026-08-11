"""Merge the retranslation batches into the applied TSV and verify the result.

Batches are separate files so the work can stop and resume, but they have to end up in one
translation.  Each entry is keyed by index and carries the corrected Japanese it was written
from, so a batch written against an older source is caught rather than applied blindly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import encode_korean
import translation_text

ROOT = Path(r"D:\psp\원격수사")
BASE = ROOT / "build" / "translation_ko_quality_checked.tsv"
JA = ROOT / "font_extract" / "script_full_ja_corrected.tsv"
SLOTS = ROOT / "build" / "korean_slots_full_clean.json"
OUT = ROOT / "build" / "translation_ko_retranslated.tsv"
REPORT = ROOT / "build" / "retranslation_apply_report.json"

FOREIGN = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\ufffd]")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batches", type=Path, default=ROOT / "build")
    args = parser.parse_args()

    header, rows = translation_text.parse_loose_tsv(BASE)
    _, ja_rows = translation_text.parse_loose_tsv(JA)
    ja = {r[0].strip().lower(): r[2] for r in ja_rows if len(r) >= 3}
    slots = {c: int(i) for c, i in
             json.loads(SLOTS.read_text(encoding="utf-8"))["slots"].items()}

    entries, files = {}, []
    for path in sorted(args.batches.glob("retranslation_batch*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for t in data["translations"]:
            entries[t["source_index"].lower()] = t
        files.append(path.name)
    print(f"{len(files)} batches, {len(entries)} translations: {files}")

    applied, mismatched, unencodable = [], [], []
    out_rows = []
    for row in rows:
        if len(row) < 3:
            out_rows.append(row)
            continue
        key = row[0].strip().lower()
        t = entries.get(key)
        if t:
            if ja.get(key, "") != t["source_ja"]:
                mismatched.append({"index": key, "expected": t["source_ja"][:70],
                                   "actual": ja.get(key, "")[:70]})
            else:
                text = t["new_translation"]
                if encode_korean.encode_text(text.replace("\\n", "\n"), slots) is None:
                    bad = sorted({c for c in text.replace("\\n", "")
                                  if c not in slots and c not in encode_korean.PASSTHROUGH})
                    unencodable.append({"index": key, "characters": bad})
                else:
                    row = [row[0], row[1], text]
                    applied.append(key)
        out_rows.append(row)

    OUT.write_text(header + "\n" + "\n".join("\t".join(r) for r in out_rows) + "\n",
                   encoding="utf-8")

    _, new_rows = translation_text.parse_loose_tsv(OUT)
    ko = {r[0].strip().lower(): r[2] for r in new_rows if len(r) >= 3}
    residual = [k for k, v in ko.items() if FOREIGN.search(v)]
    fails = [k for k, v in ko.items()
             if encode_korean.encode_text(v.replace("\\n", "\n"), slots) is None]

    report = {
        "schema": "enkaku_retranslation_apply_v1",
        "batches": files, "translations_available": len(entries),
        "applied": len(applied), "source_mismatch": mismatched,
        "unencodable": unencodable,
        "rows": len(ko), "indices_match_source": set(ko) == set(ja),
        "residual_foreign_rows": len(residual),
        "encoding_failures": len(fails),
        "output": str(OUT),
        "sha256": hashlib.sha256(OUT.read_bytes()).hexdigest(),
        "emulator_launched": False,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"applied {len(applied)}, source mismatch {len(mismatched)}, "
          f"unencodable {len(unencodable)}")
    print(f"rows {len(ko)}, indices match source: {report['indices_match_source']}")
    print(f"residual foreign-script rows {len(residual)}, encoding failures {len(fails)}")
    print(f"sha256 {report['sha256']}")
    print(f"-> {OUT}\n-> {REPORT}")


if __name__ == "__main__":
    main()

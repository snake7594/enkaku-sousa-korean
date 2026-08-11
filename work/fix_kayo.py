"""Correct the mother's name from 가쓰요 to 가요, on the evidence of the name plate.

The script decodes her as 斉藤勝代, and the translation follows that with 가쓰요.  The name
plate is a picture -- no glyph table between it and the player -- and it reads 斉藤佳代.  An
image cannot be misread by a charmap, so 佳 is the character and かよ the reading; 勝 is one
more slot the map has wrong.

This is also the name that could not be settled earlier: her only ruby is 斉《お》藤《ふ》
衢《く》代《ろ》, a pun spelling おふくろ, which forces each kana to the joke rather than to
the kanji.  The plate settles what the ruby could not.

Only the standalone name is replaced, and only where the Japanese for that row actually
contains 勝代 -- 가쓰 appears in other words and a blanket substitution would hit them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")
JA = ROOT / "font_extract" / "script_full_ja_corrected.tsv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tsv", type=Path,
                        default=ROOT / "build" / "translation_ko_retranslated_v2.tsv")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "build" / "translation_ko_v2_kayo.tsv")
    parser.add_argument("--report", type=Path,
                        default=ROOT / "build" / "kayo_fix_report.json")
    args = parser.parse_args()

    _, ja_rows = translation_text.parse_loose_tsv(JA)
    ja = {r[0].strip().lower(): r[2] for r in ja_rows if len(r) >= 3}
    header, rows = translation_text.parse_loose_tsv(args.tsv)

    changed, skipped, out = [], [], []
    for row in rows:
        if len(row) < 3 or "가쓰요" not in row[2]:
            out.append(row)
            continue
        key = row[0].strip().lower()
        source = ja.get(key, "")
        if "勝代" not in source and "佳代" not in source:
            skipped.append({"index": key, "ja": source[:70], "ko": row[2][:70]})
            out.append(row)
            continue
        text = row[2].replace("가쓰요", "가요")
        changed.append({"index": key, "before": row[2][:70], "after": text[:70]})
        out.append([row[0], row[1], text])

    args.out.write_text(header + "\n" + "\n".join("\t".join(r) for r in out) + "\n",
                        encoding="utf-8")
    args.report.write_text(json.dumps({
        "schema": "enkaku_kayo_fix_v1",
        "evidence": "name plate tex0346 reads 斉藤佳代; the script decodes 勝代",
        "changed": len(changed), "skipped_no_source_name": len(skipped),
        "changes": changed, "skipped": skipped,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(changed)} rows changed, {len(skipped)} left alone "
          f"(no 勝代/佳代 in the source)")
    for c in changed[:4]:
        print(f"   {c['index']}\n     - {c['before']}\n     + {c['after']}")
    print(f"-> {args.out}\n-> {args.report}")


if __name__ == "__main__":
    main()

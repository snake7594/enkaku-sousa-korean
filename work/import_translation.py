"""Turn the project's translation overrides into a TSV the encoder can consume.

`translation_overrides.json` normally keys its entries by row order, but the project also
keeps a Japanese-text keyed table for repeated and late-added rows.  The importer uses the
row key first and the current applied-Japanese text as a checked fallback, so a regenerated
script cannot silently drop translations merely because an earlier charmap pass changed a
glyph spelling.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

FONT = Path(r"D:\psp\원격수사\font_extract")


def load_rows(path: Path) -> list[list[str]]:
    return [l.split("\t") for l in path.read_text(encoding="utf-8").splitlines()[1:] if l.strip()]


def normalise(text: str) -> str:
    """Strip things that differ between generations but not in meaning."""
    text = text.replace("\\n", "").replace("\n", "")
    text = re.sub(r"《[^》]*》", "", text)      # ruby readings
    text = re.sub(r"\[\d+\]", "", text)          # unresolved glyph placeholders
    return text.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overrides", type=Path, default=FONT / "translation_overrides.json")
    parser.add_argument("--raw", type=Path, default=FONT / "script_full_raw.tsv")
    parser.add_argument("--ja", type=Path, default=FONT / "script_full_ja.tsv")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    data = json.loads(args.overrides.read_text(encoding="utf-8"))
    by_order = data.get("by_order", {})
    by_text = data.get("by_japanese_applied", {})
    raw_rows = load_rows(args.raw)
    ja_rows = load_rows(args.ja)
    print(f"{len(by_order)} translated entries, {len(raw_rows)} script rows")

    matched = mismatched = missing = 0
    problems = []
    out_lines = ["offset\tlines\ttext"]
    for key, entry in sorted(by_order.items(), key=lambda kv: int(kv[0])):
        index = int(key)
        if index >= len(raw_rows):
            missing += 1
            continue
        source = ja_rows[index][2] if index < len(ja_rows) else ""
        selected = entry or by_text.get(source)
        if isinstance(selected, str):
            selected = {"korean": selected}
        selected = selected or {}
        korean = (selected.get("korean") or "").strip()
        if not korean:
            missing += 1
            continue
        reviewed = selected.get("japanese_reviewed") or ""
        current = source

        # alignment check: the Japanese it was translated from should still be this row
        a, b = normalise(reviewed), normalise(current)
        if a and b:
            overlap = len(set(a) & set(b)) / max(1, len(set(a)))
            if overlap < 0.5:
                mismatched += 1
                problems.append((index, a[:28], b[:28]))
                continue
        matched += 1
        offset = raw_rows[index][0]
        lines = korean.count("\\n") + 1
        out_lines.append(f"{offset}\t{lines}\t{korean}")

    args.out.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"   aligned {matched}, misaligned {mismatched}, missing translation {missing}")
    print(f"-> {args.out} ({len(out_lines) - 1} rows)")

    if problems:
        print("\nfirst alignment problems (index / translated-from / current row):")
        for index, a, b in problems[:8]:
            print(f"   {index:5d}  {a}  |  {b}")
    if args.report:
        args.report.write_text("\n".join(f"{i}\t{a}\t{b}" for i, a, b in problems),
                               encoding="utf-8")


if __name__ == "__main__":
    main()

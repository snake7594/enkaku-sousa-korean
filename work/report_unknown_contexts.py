"""Print evidence for unresolved glyphs from raw script and ruby annotations.

This is a read-only investigation helper.  It applies the character-level
confirmations in charmap_additional_confirmed.json only for display; the raw
script remains the authority.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHARMAP = ROOT / "font_extract" / "charmap_final.json"
RAW = ROOT / "font_extract" / "script_full_raw.tsv"
RUBY = ROOT / "font_extract" / "ruby_pairs.json"
ADDITIONAL = ROOT / "font_extract" / "charmap_additional_confirmed.json"
TOKEN = re.compile(r"\[(\d+)\]")


def load_map() -> dict[int, str]:
    entries = json.loads(CHARMAP.read_text(encoding="utf-8"))
    result = {int(x["index"]): x["char"] for x in entries}
    if ADDITIONAL.exists():
        extra = json.loads(ADDITIONAL.read_text(encoding="utf-8"))
        for item in extra.get("character_confirmations", []):
            ids = item.get("glyph_indices", [])
            confirmed = item.get("confirmed", "")
            if len(ids) == len(confirmed):
                result.update(zip(ids, confirmed))
    return result


def decode(text: str, mapping: dict[int, str]) -> str:
    return TOKEN.sub(lambda m: mapping.get(int(m.group(1)), f"□{m.group(1)}□"), text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("indices", nargs="+", type=int)
    parser.add_argument("--rows", type=int, default=14)
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    wanted = set(args.indices)
    mapping = load_map()
    entries = json.loads(CHARMAP.read_text(encoding="utf-8"))
    info = {int(x["index"]): x for x in entries}
    rows: list[tuple[int, str, str]] = []
    with RAW.open(encoding="utf-8", newline="") as fh:
        for order, row in enumerate(csv.DictReader(fh, delimiter="\t")):
            text = row["text"]
            ids = {int(x) for x in TOKEN.findall(text)}
            if wanted & ids:
                rows.append((order, row.get("offset", ""), text))

    ruby = json.loads(RUBY.read_text(encoding="utf-8"))
    for index in args.indices:
        x = info.get(index, {})
        print(f"\n=== [{index}] current={x.get('char')!r} source={x.get('source')} confidence={x.get('confidence')} uses={x.get('uses')} ===")
        pairs = [p for p in ruby if index in p.get("base", [])]
        for p in sorted(pairs, key=lambda p: (-p.get("count", 0), p.get("reading", "")))[:20]:
            print(f"RUBY count={p.get('count')}: {p.get('base')} -> {p.get('reading')}")
        selected = rows if args.all else rows[: args.rows]
        for order, offset, raw in selected:
            if index in {int(x) for x in TOKEN.findall(raw)}:
                print(f"{order:5d} off={offset:8s}  {decode(raw, mapping)}")
        if not selected:
            print("(no rows)")


if __name__ == "__main__":
    main()

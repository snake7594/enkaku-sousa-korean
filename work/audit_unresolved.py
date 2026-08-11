"""Build a review ledger for every still-unconfirmed game glyph.

The ledger is deliberately evidentiary rather than predictive: it keeps the
exact indexed source row, the current best Japanese rendering, ruby readings,
frequency, and alternatives together so a proposed Kanji can be checked
against all of its uses before it is promoted to the confirmation ledger.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "font_extract"
TOKEN = re.compile(r"\[(\d+)\]")


def load_map() -> tuple[dict[int, str], set[int]]:
    entries = json.loads((FONT / "charmap_final.json").read_text(encoding="utf-8"))
    mapping = {int(item["index"]): item["char"] for item in entries}
    confirmed: set[int] = set()
    extra_path = FONT / "charmap_additional_confirmed.json"
    if extra_path.exists():
        extra = json.loads(extra_path.read_text(encoding="utf-8"))
        for group in ("character_confirmations", "phrase_confirmations"):
            for item in extra.get(group, []):
                indices = item.get("glyph_indices", [])
                text = item.get("confirmed", "")
                if len(indices) != len(text):
                    continue
                for index, char in zip(indices, text):
                    mapping[int(index)] = char
                    confirmed.add(int(index))
    return mapping, confirmed


def decode(text: str, mapping: dict[int, str], focus: int | None = None) -> str:
    def replace(match: re.Match[str]) -> str:
        index = int(match.group(1))
        if focus == index:
            return f"□{index}□"
        return mapping.get(index, f"□{index}□")

    return TOKEN.sub(replace, text)


def main() -> None:
    mapping, confirmed = load_map()
    charmap = json.loads((FONT / "charmap_final.json").read_text(encoding="utf-8"))
    unresolved = {
        int(item["index"]): item
        for item in charmap
        if item.get("source") == "bitmap" and int(item["index"]) not in confirmed
    }

    with (FONT / "script_full_raw.tsv").open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    uses = Counter(int(index) for row in rows for index in TOKEN.findall(row["text"]))
    charmap_indices = {int(item["index"]) for item in charmap}
    out_of_range_indices = sorted(index for index in uses if index not in charmap_indices)
    contexts: dict[int, list[dict[str, object]]] = defaultdict(list)
    for order, row in enumerate(rows):
        indices = {int(index) for index in TOKEN.findall(row["text"])}
        for index in unresolved.keys() & indices:
            contexts[index].append(
                {
                    "order": order,
                    "offset": row["offset"],
                    "raw_indexed": row["text"],
                    "japanese_context": decode(row["text"], mapping, focus=index),
                }
            )

    ruby_pairs = json.loads((FONT / "ruby_pairs.json").read_text(encoding="utf-8"))
    ruby_by_index: dict[int, list[dict[str, object]]] = defaultdict(list)
    for pair in ruby_pairs:
        base = [int(index) for index in pair.get("base", [])]
        for index in set(base) & unresolved.keys():
            ruby_by_index[index].append(
                {
                    "base": base,
                    "reading": pair.get("reading", ""),
                    "count": pair.get("count", 0),
                    "decoded_base": "".join(mapping.get(glyph, f"□{glyph}□") for glyph in base),
                }
            )

    items = []
    for index, item in unresolved.items():
        ruby = sorted(
            ruby_by_index.get(index, []),
            key=lambda value: (-int(value.get("count", 0)), str(value.get("reading", ""))),
        )
        items.append(
            {
                "index": index,
                "current_char": item.get("char"),
                "source": item.get("source"),
                "confidence": item.get("confidence"),
                "uses_in_script": uses.get(index, 0),
                "uses_in_charmap": item.get("uses"),
                "alternatives": item.get("alts", []),
                "ruby_evidence": ruby[:30],
                "ruby_evidence_count": len(ruby),
                "contexts": contexts.get(index, [])[:60],
                "context_count": len(contexts.get(index, [])),
                "status": "unconfirmed",
            }
        )
    items.sort(key=lambda value: (-int(value["uses_in_script"]), int(value["index"])))

    # The late script contains a small extension range that is not represented
    # in charmap_final.json.  Keep it in a separate section so a confirmed
    # contextual extension is not reported as unresolved, while test-only or
    # genuinely missing slots remain visible to Claude Code.
    out_of_range_items = []
    for index in out_of_range_indices:
        row_contexts = []
        game_dialogue_uses = 0
        test_only = True
        for order, row in enumerate(rows):
            if f"[{index}]" not in row["text"]:
                continue
            is_test = "テスト" in row["text"] or "改ページ" in row["text"]
            test_only = test_only and is_test
            if not is_test:
                game_dialogue_uses += row["text"].count(f"[{index}]")
            row_contexts.append(
                {
                    "order": order,
                    "offset": row["offset"],
                    "raw_indexed": row["text"],
                    "japanese_context": decode(row["text"], mapping, focus=index),
                }
            )
        is_confirmed = index in confirmed
        out_of_range_items.append(
            {
                "index": index,
                "current_char": mapping.get(index),
                "source": "missing_from_charmap",
                "confidence": "high" if is_confirmed else "unresolved",
                "uses_in_script": uses.get(index, 0),
                "uses_in_charmap": None,
                "alternatives": [],
                "ruby_evidence": [],
                "ruby_evidence_count": 0,
                "contexts": row_contexts[:60],
                "context_count": len(row_contexts),
                "game_dialogue_uses": game_dialogue_uses,
                "test_only": test_only,
                "status": (
                    "confirmed_context_extension"
                    if is_confirmed
                    else "unconfirmed_test_only"
                    if test_only
                    else "unconfirmed_missing_from_charmap"
                ),
            }
        )

    data = {
        "schema": "enkaku-sousa-unresolved-kanji-audit/v1",
        "purpose": "Claude Code용 미확정 글리프 검증 장부. 예측값이 아니라 원문·후리가나·반복 문맥을 보존한다.",
        "generated_from": {
            "raw_script": "font_extract/script_full_raw.tsv",
            "charmap": "font_extract/charmap_final.json",
            "ruby_pairs": "font_extract/ruby_pairs.json",
            "additional_confirmations": "font_extract/charmap_additional_confirmed.json",
        },
        "stats": {
            "unresolved_count": len(items),
            "unresolved_script_occurrences": sum(int(item["uses_in_script"]) for item in items),
            "with_ruby": sum(bool(item["ruby_evidence"]) for item in items),
            "without_ruby": sum(not item["ruby_evidence"] for item in items),
            "out_of_range_glyph_count": len(out_of_range_items),
            "out_of_range_confirmed_count": sum(item["status"] == "confirmed_context_extension" for item in out_of_range_items),
            "out_of_range_unconfirmed_count": sum(item["status"] != "confirmed_context_extension" for item in out_of_range_items),
            "out_of_range_script_occurrences": sum(int(item["uses_in_script"]) for item in out_of_range_items),
            "out_of_range_unconfirmed_script_occurrences": sum(
                int(item["uses_in_script"])
                for item in out_of_range_items
                if item["status"] != "confirmed_context_extension"
            ),
            "out_of_range_unconfirmed_game_dialogue_occurrences": sum(
                int(item["game_dialogue_uses"])
                for item in out_of_range_items
                if item["status"] != "confirmed_context_extension"
            ),
        },
        "items": items,
        "out_of_range_glyphs": out_of_range_items,
    }
    out = FONT / "unresolved_kanji_audit.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    print(json.dumps(data["stats"], ensure_ascii=False))
    print("top unresolved:")
    for item in items[:30]:
        print(
            f"[{item['index']}] uses={item['uses_in_script']} "
            f"ruby={item['ruby_evidence_count']} current={item['current_char']}"
        )
    print("out-of-range glyphs:")
    for item in out_of_range_items:
        print(
            f"[{item['index']}] uses={item['uses_in_script']} "
            f"status={item['status']} current={item['current_char']}"
        )


if __name__ == "__main__":
    main()

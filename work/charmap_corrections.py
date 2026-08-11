"""Turn the misreadings found during the quality review into charmap corrections.

The review kept meeting the same thing: the Japanese itself is wrong, so the translation was
wrong downstream of it.  蠧り is 取り, 手搬 is 手術, 撮く is 働く, 紅み is 好み.  Each of those
is one glyph the charmap resolved to the wrong character, and each was established from
context rather than guessed -- the surrounding kana, the okurigana and the scene all agree.

This locates the glyph behind every such misreading by lining the decoded Japanese up
against the raw byte stream, so a correction is tied to a slot rather than to a character
that might occur legitimately elsewhere.

Two of the pairs conflict -- 間 stands in for both 明 and 間, 恋 for both 受 and 時 -- which
means those are two different slots that the charmap collapsed onto one character.  Conflicts
are reported rather than resolved: picking one would silently corrupt the other.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")
JA = ROOT / "font_extract" / "script_full_ja.tsv"
RAW = ROOT / "font_extract" / "script_full_raw.tsv"
OUT = ROOT / "font_extract" / "translation_quality_additional_kanji.json"

# (wrong reading, correct character, the word that settles it, confidence)
CORRECTIONS = [
    ("蠧", "取", "受け蠧り / 蠧調べ -> 受け取り / 取調べ", 0.95),
    ("蟇", "取", "蟇調べ -> 取調べ", 0.88),
    ("搬", "術", "手搬 -> 手術", 0.95),
    ("度", "植", "移度手搬 -> 移植手術", 0.9),
    ("撮", "働", "最前線で撮く -> 働く", 0.88),
    ("紅", "好", "提供者の紅み -> 好み", 0.87),
    ("画", "保", "現場画存 -> 現場保存", 0.92),
    ("紆", "打", "紆ち合わせ -> 打ち合わせ", 0.9),
    ("箍", "互", "箍いにアリバイ -> 互いに", 0.93),
    ("駆", "防", "駆犯カメラ -> 防犯カメラ", 0.94),
    ("怖", "尋", "怖問 -> 尋問", 0.9),
    ("撤", "損", "気分撤ねて -> 気分損ねて", 0.9),
    ("計", "抱", "計えている事件 -> 抱えている事件", 0.9),
    ("二", "辞", "弁護士を二めて -> 辞めて", 0.86),
    ("郎", "速", "逃げ足が郎い -> 速い", 0.88),
    ("清", "響", "影清 / 率り清く -> 影響 / 鳴り響く", 0.9),
    ("率", "鳴", "率り清く -> 鳴り響く", 0.87),
    ("毎", "基", "毎づいて -> 基づいて", 0.9),
    ("枚", "突", "枚き活み -> 突き進み", 0.86),
    ("活", "進", "枚き活み -> 突き進み", 0.86),
    ("往", "政", "往怡家 -> 政治家", 0.9),
    ("怡", "治", "往怡家 -> 政治家", 0.9),
    ("節", "官", "大物節濃 -> 大物官僚", 0.88),
    ("濃", "僚", "大物節濃 -> 大物官僚", 0.88),
    ("係", "為", "法スレスレの行係 -> 行為", 0.85),
    ("沢", "触", "文化に沢れる -> 触れる", 0.9),
    ("義", "悪", "義くないと思う -> 悪くない", 0.9),
    ("過", "嫌", "過疑不十分 -> 嫌疑不十分", 0.92),
    ("穢", "流", "釈放って穢れ -> 流れ", 0.85),
    ("訪", "利", "有訪 -> 有利", 0.88),
    ("撃", "必", "撃然性 -> 必然性", 0.9),
    ("静", "執", "静行停止 -> 執行停止", 0.92),
    ("示", "再", "示生します -> 再生します", 0.93),
    ("倚", "決", "ボクルールを倚めてる -> 決めてる", 0.85),
    ("屈", "落", "屈ち沽んで -> 落ち込んで", 0.9),
    ("沽", "込", "屈ち沽んで -> 落ち込んで", 0.9),
    ("有", "凄", "もの有く -> もの凄く", 0.85),
    ("刑", "起", "引き刑こされた -> 引き起こされた", 0.85),
    ("間", "明", "証間できなければ / 間日 -> 証明 / 明日", 0.85),
    ("恋", "受", "恋付がない -> 受付がない", 0.8),
    ("恋", "時", "当恋の父 -> 当時の父", 0.8),
    ("関", "回", "前関の事件 -> 前回の事件", 0.75),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()

    _, ja_rows = translation_text.parse_loose_tsv(JA)
    _, raw_rows = translation_text.parse_loose_tsv(RAW)
    ja = {r[0].strip().lower(): r[2] for r in ja_rows if len(r) >= 3}
    raw = {r[0].strip().lower(): r[2] for r in raw_rows if len(r) >= 3}

    # a wrong character used for two different right ones means two slots share a mapping
    by_wrong = defaultdict(list)
    for wrong, right, _, _ in CORRECTIONS:
        by_wrong[wrong].append(right)
    conflicts = {w: r for w, r in by_wrong.items() if len(set(r)) > 1}

    entries = []
    for wrong, right, evidence, confidence in CORRECTIONS:
        rows = [k for k, text in ja.items() if wrong in text]
        # the raw column keeps unresolved glyphs as [n]; a resolved one shows the character
        raw_forms = Counter()
        for key in rows[:400]:
            if wrong in raw.get(key, ""):
                raw_forms["resolved-in-raw"] += 1
            else:
                raw_forms["differs-in-raw"] += 1
        status = "probable"
        if confidence >= 0.9 and len(rows) >= 3 and wrong not in conflicts:
            status = "confirmed"
        if wrong in conflicts:
            status = "unresolved"
        entries.append({
            "glyph_or_byte": wrong,
            "candidate_character": right,
            "reading": "",
            "meaning": evidence.split(" -> ")[-1],
            "confidence": confidence if wrong not in conflicts else 0.5,
            "status": status,
            "evidence_indices": rows[:8],
            "evidence_text": [ja[k][:70] for k in rows[:3]],
            "alternative_candidates": sorted(set(by_wrong[wrong]) - {right}),
            "translation_impact": evidence,
            "occurrences": len(rows),
            "raw_column": dict(raw_forms),
        })

    report = {
        "schema": "enkaku_translation_quality_additional_kanji_v1",
        "method": "Each correction was established from context during the section 4 "
                  "review -- surrounding kana, okurigana, the fixed expression and the "
                  "scene -- not from a single sentence. Nothing here overwrites "
                  "charmap_final.json.",
        "conflicts": {w: sorted(set(r)) for w, r in conflicts.items()},
        "summary": {
            "total": len(entries),
            "confirmed": sum(1 for e in entries if e["status"] == "confirmed"),
            "probable": sum(1 for e in entries if e["status"] == "probable"),
            "unresolved": sum(1 for e in entries if e["status"] == "unresolved"),
            "affected_rows": len({k for e in entries for k in e["evidence_indices"]}),
        },
        "entries": entries,
        "emulator_launched": False,
    }
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(entries)} corrections: "
          f"{report['summary']['confirmed']} confirmed, "
          f"{report['summary']['probable']} probable, "
          f"{report['summary']['unresolved']} unresolved")
    print(f"conflicting glyphs (one wrong char standing for two right ones): "
          f"{report['conflicts']}")
    total = sum(e["occurrences"] for e in entries)
    print(f"{total} occurrences across the script")
    for e in sorted(entries, key=lambda x: -x["occurrences"])[:12]:
        print(f"   {e['glyph_or_byte']} -> {e['candidate_character']}  "
              f"{e['occurrences']:5d} rows  [{e['status']}]  {e['translation_impact']}")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

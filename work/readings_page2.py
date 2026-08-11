"""Slot readings taken from build/dup_page2.png, the last of the three sheets."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
MAP = ROOT / "font_extract" / "charmap_quality_corrected.json"
REPORT = ROOT / "build" / "charmap_glyph_readings.json"

READINGS = {
    1002: "歳", 1004: "迫", 1007: "漏", 1017: "拗", 1027: "練", 1036: "晋",
    1038: "舞", 1046: "荷", 1047: "倶", 1048: "襲", 1055: "棄", 1063: "闇",
    1069: "略", 1070: "贄", 1072: "低", 1084: "距", 1095: "焦", 1099: "研",
    1104: "皮", 1107: "覆", 1111: "辻", 1116: "暴", 1117: "伴", 1120: "珍",
    1127: "捉", 1128: "滑", 1129: "未", 1131: "短", 1138: "懲", 1143: "憑",
    1147: "般", 1150: "睨", 1154: "権", 1164: "諦", 1168: "渉", 1174: "円",
    1176: "誤", 1183: "翌", 1185: "更", 1193: "貼", 1195: "詫", 1196: "繰",
    1199: "百", 1208: "溜", 1211: "稼", 1226: "系", 1231: "爽", 1232: "薬",
    1238: "殊", 1245: "愁", 1249: "遥", 1252: "婆", 1254: "囚", 1259: "腸",
    1271: "版", 1272: "湯", 1287: "呑", 1295: "癒", 1300: "史", 1315: "絵",
    1316: "弾", 1323: "逐", 1334: "蜘", 1335: "蛛", 1341: "奮", 1346: "育",
    1350: "毒", 1351: "遂", 1353: "猶", 1356: "悶", 1361: "妬", 1362: "泡",
    1365: "漢",
}


def main() -> None:
    charmap = json.loads(MAP.read_text(encoding="utf-8"))
    changed = []
    for slot, char in READINGS.items():
        before = charmap[slot].get("char")
        if before == char:
            continue
        charmap[slot] = {**charmap[slot], "char": char, "source": "glyph_image_reading",
                         "confidence": "high", "previous_char": before}
        changed.append({"slot": slot, "from": before, "to": char,
                        "uses": charmap[slot].get("uses", 0)})
    MAP.write_text(json.dumps(charmap, ensure_ascii=False, indent=1), encoding="utf-8")

    old = json.loads(REPORT.read_text(encoding="utf-8"))
    old["changed"] += changed
    old["total_uses_affected"] = sum(c["uses"] for c in old["changed"])
    old["pages_read"] = ["dup_page0.png", "dup_page1.png", "dup_page2.png"]
    old["duplicate_slots_total"] = 423
    REPORT.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding="utf-8")

    # nothing should still share a character after this
    from collections import Counter
    dup = Counter(e["char"] for e in charmap if e.get("char"))
    remaining = {c: n for c, n in dup.items() if n > 1}
    print(f"page 2: {len(changed)} slots reassigned, "
          f"{sum(c['uses'] for c in changed)} uses")
    print(f"cumulative: {len(old['changed'])} slots, {old['total_uses_affected']} uses")
    print(f"characters still on more than one slot: {len(remaining)} "
          f"{sorted(remaining.items(), key=lambda kv: -kv[1])[:8]}")


if __name__ == "__main__":
    main()

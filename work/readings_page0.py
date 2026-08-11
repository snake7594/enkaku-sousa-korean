"""Slot readings taken from build/dup_page0.png, applied to the corrected charmap.

Read off the rendered bitmaps one cell at a time against the slot list the sheet printed.
Only slots whose glyph differs from the character the charmap assigned are listed; the rest
were checked and found correct, which is itself worth knowing -- roughly half of the
duplicate slots are right, so the map is not uniformly broken, it has a specific fault.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
MAP = ROOT / "font_extract" / "charmap_quality_corrected.json"
REPORT = ROOT / "build" / "charmap_glyph_readings.json"

# slot -> the character its bitmap actually draws
READINGS = {
    43: "首", 95: "恐", 103: "回", 125: "笑", 133: "南", 185: "親", 208: "集",
    220: "遣", 225: "欲", 239: "疲", 243: "佳", 246: "赤", 255: "局", 256: "動",
    263: "締", 270: "繁", 280: "間", 281: "広", 295: "机", 296: "椅", 297: "呼",
    303: "難", 304: "夢", 305: "凝", 311: "訪", 314: "利", 315: "葉", 330: "頂",
    332: "御", 334: "建", 335: "設", 338: "望", 340: "計", 342: "階", 347: "制",
    348: "整", 349: "柔", 360: "格", 361: "進", 364: "常", 371: "謎", 372: "解",
    373: "三", 374: "浦", 386: "端", 392: "走", 402: "横", 410: "貴", 411: "重",
    415: "世", 419: "弊", 423: "個", 424: "扱", 429: "月", 433: "司", 434: "緊",
    437: "訳", 445: "台", 446: "壊", 447: "速", 449: "約", 450: "束", 455: "員",
    460: "娘", 462: "環", 464: "転", 482: "二", 486: "凄", 487: "喜", 488: "兵",
    492: "奇", 499: "満", 500: "画",
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
    old["pages_read"] = ["dup_page0.png"]
    REPORT.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"page 0: {len(changed)} more slots reassigned, "
          f"{sum(c['uses'] for c in changed)} uses")
    print(f"cumulative: {len(old['changed'])} slots, "
          f"{old['total_uses_affected']} uses")
    for c in sorted(changed, key=lambda x: -x["uses"])[:12]:
        print(f"   slot {c['slot']:5d}  {c['from']} -> {c['to']}   ({c['uses']} uses)")


if __name__ == "__main__":
    main()

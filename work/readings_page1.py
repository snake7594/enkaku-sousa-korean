"""Slot readings taken from build/dup_page1.png.

Three of these confirm guesses the quality review had made from context alone -- 濃 is 僚,
率 is 鳴, 刑 is 起 -- which is a useful check on the earlier method: context got those right
but could not tell which of two slots to change, and could not see the ones it never met.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
MAP = ROOT / "font_extract" / "charmap_quality_corrected.json"
REPORT = ROOT / "build" / "charmap_glyph_readings.json"

READINGS = {
    510: "乗", 512: "義", 514: "弱", 519: "枚", 523: "恨", 524: "偽", 528: "驚",
    530: "貢", 533: "恩", 549: "返", 553: "辱", 566: "簡", 567: "単", 568: "清",
    579: "稚", 596: "潔", 601: "電", 612: "針", 613: "筋", 617: "複", 625: "固",
    642: "学", 644: "羨", 663: "堅", 666: "宮", 667: "銀", 676: "音", 677: "鳴",
    684: "測", 686: "備", 696: "起", 707: "杯", 709: "据", 718: "温", 719: "厚",
    730: "命", 733: "熱", 734: "惚", 736: "築", 739: "含", 741: "尊", 744: "播",
    745: "磨", 746: "潰", 748: "粧", 756: "箱", 768: "肌", 774: "楽", 780: "若",
    786: "順", 790: "剤", 792: "耳", 793: "看", 798: "吸", 819: "薄", 823: "島",
    826: "種", 831: "息", 834: "逝", 840: "姿", 844: "妙", 848: "惜", 851: "飛",
    870: "位", 871: "僚", 872: "埃", 875: "齢", 880: "波", 884: "道", 886: "演",
    889: "鏡", 892: "背", 898: "裁", 922: "沢", 923: "曹", 929: "怨", 934: "析",
    945: "励", 946: "資", 948: "振", 949: "戒", 958: "詰", 960: "請", 962: "規",
    965: "青", 966: "浸", 972: "眺", 973: "簿",
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
    old["pages_read"] = ["dup_page0.png", "dup_page1.png"]
    REPORT.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"page 1: {len(changed)} slots reassigned, "
          f"{sum(c['uses'] for c in changed)} uses")
    print(f"cumulative: {len(old['changed'])} slots, {old['total_uses_affected']} uses")
    for c in sorted(changed, key=lambda x: -x["uses"])[:10]:
        print(f"   slot {c['slot']:5d}  {c['from']} -> {c['to']}   ({c['uses']} uses)")


if __name__ == "__main__":
    main()

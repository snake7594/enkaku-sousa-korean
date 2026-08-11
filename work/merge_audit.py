"""Add the low-use half of the glyph audit to charmap_glyph_audit.json.

The first pass covered the 418 slots used 20 or more times.  These are the remaining 646,
used between once and nineteen times, rendered and read the same way.  212 of them were
wrong, which is a higher rate than the common slots -- unsurprising, since a rare character
gives context guessing almost nothing to work from.

Several land in sentences that were visibly broken: 埋 restores 応接室が埋《う》まっている,
祈 restores 祈《いの》っています, 厳 restores もっと厳しく指導すべきでした, 案 restores
引っ込み思案, 滅 restores 自滅《じめつ》, 妹 restores 姉妹, 晴 restores 容疑が晴れる, and
盛 restores 繁盛《はんじょう》.

Two glyphs -- 1281 and 1286 -- could not be read with confidence at any magnification and are
deliberately left as they are rather than guessed at.
"""

from __future__ import annotations

import json
from pathlib import Path

FONT = Path(r"D:\psp\원격수사") / "font_extract"

# slot: character, read off the rendered glyph
NEW = {
    54: "興", 569: "弟", 631: "霞", 689: "崩", 266: "並", 511: "越", 560: "頭", 355: "晴",
    570: "継", 723: "妹", 801: "医", 815: "況", 563: "座", 259: "各", 290: "与", 367: "敵",
    438: "等",
    795: "詳", 891: "閉", 1012: "泣", 384: "厳", 436: "案", 681: "仮", 516: "寄", 616: "替",
    752: "静", 874: "除", 1062: "延",
    829: "滅", 944: "激", 976: "公", 1092: "授", 381: "注", 561: "勢", 887: "届", 319: "料",
    507: "買", 580: "為", 589: "困", 703: "照", 894: "及",
    1109: "材", 284: "芽", 405: "積", 536: "抗", 559: "乱", 711: "叫", 809: "濡", 1049: "週",
    1187: "偉", 245: "妻", 520: "撮", 614: "添", 632: "神", 828: "祈", 1000: "掴", 1039: "懐",
    865: "混", 1031: "糸", 1093: "浮", 1159: "差", 1179: "憎", 207: "似", 265: "街", 278: "吹",
    551: "腹", 556: "技", 591: "忍", 611: "譲",
    1003: "討", 1078: "裕", 1123: "預", 1130: "勧", 359: "兼", 376: "恥", 597: "八", 610: "益",
    674: "遭", 713: "準", 716: "達", 747: "巡", 895: "堪", 1086: "揉", 1098: "聴", 1106: "伏",
    1119: "北",
    1262: "繋", 1333: "荘", 1366: "肢", 271: "盛", 325: "駅", 398: "株", 505: "飯", 548: "痛",
    802: "油", 806: "踏", 811: "易", 918: "馴", 920: "湧", 954: "団", 1013: "平",
    1041: "払", 1083: "勇", 1105: "肉", 1115: "掻", 1118: "舐", 1175: "詭", 1214: "胸",
    1236: "里", 1257: "僕", 1267: "狭", 1273: "黒", 1274: "船", 269: "堂", 307: "冊", 471: "臭",
    491: "統", 494: "耐", 501: "拝", 504: "茶", 565: "敏", 717: "荒", 765: "健", 789: "抑",
    800: "踊", 885: "穴", 914: "米",
    924: "羽", 961: "県", 995: "秒", 1006: "超", 1019: "歯", 1021: "染", 1044: "宛", 1052: "句",
    1059: "慰", 1082: "怯", 1110: "把", 1133: "景", 1186: "僧", 1206: "殴", 1228: "偏",
    1229: "敷", 1233: "夏", 1244: "粋", 1261: "併",
    1264: "飢", 1304: "贖", 1305: "錯", 1307: "避", 1309: "祝", 1313: "核", 1344: "騙",
    399: "創", 531: "献", 544: "松", 622: "甲", 623: "斐", 722: "販", 818: "徴", 820: "衛",
    824: "埋", 827: "彩", 841: "鍛", 862: "濃",
    909: "馳", 952: "鈴", 971: "往", 978: "招", 982: "躍", 987: "轟", 989: "瞭", 996: "拍",
    1005: "節", 1018: "呆", 1064: "匹", 1073: "虫", 1080: "氏", 1087: "棒", 1121: "媒",
    1124: "稿", 1132: "疎", 1136: "航", 1145: "陥", 1151: "幕", 1153: "塗", 1163: "末",
    1209: "昼", 1219: "鉄", 1221: "損", 1237: "賞", 1250: "投", 1258: "虚", 1269: "孤",
    1270: "勿", 1278: "訓", 1280: "福", 1282: "棚", 1288: "喉", 1289: "渇", 1291: "噛",
    1292: "狂", 1293: "層", 1297: "浴", 1298: "較", 1303: "潜", 1306: "絆", 1308: "癖",
    1310: "鼓", 1314: "誇",
}

NOTES = {
    824: "応接室が埋《う》まっている", 828: "祈《いの》っています",
    384: "もっと厳しく指導すべきでした", 436: "引っ込み思案", 829: "自滅《じめつ》",
    723: "姉妹", 355: "容疑が晴れる", 271: "繁盛《はんじょう》",
    325: "駅 lives here, which is why 970 is free to be 樋",
}


def main() -> None:
    path = FONT / "charmap_glyph_audit.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    quality = json.loads((FONT / "charmap_quality_corrected.json").read_text(encoding="utf-8"))
    was = {int(e["index"]): e["char"] for e in quality}

    have = {int(e["slot"]) for e in data["readings"]}
    added = 0
    for slot, char in NEW.items():
        if slot in have:
            continue
        entry = {"slot": slot, "char": char, "was": was.get(slot)}
        if slot in NOTES:
            entry["note"] = NOTES[slot]
        data["readings"].append(entry)
        added += 1

    data["readings"].sort(key=lambda e: e["slot"])
    data["unread"] = {"1281": "illegible at every magnification, left as it stands",
                      "1286": "illegible at every magnification, left as it stands"}
    data["coverage"] = ("all 1064 slots that carry text and had never been read from the "
                        "image: 418 used 20+ times, 646 used 1-19 times")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{added} readings added, {len(data['readings'])} in the file")


if __name__ == "__main__":
    main()

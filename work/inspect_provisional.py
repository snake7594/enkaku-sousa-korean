"""Decode selected raw-script rows with a temporary context map.

This helper is deliberately non-authoritative: it does not edit the final
charmap.  It is used to check whether a proposed character produces a
consistent Japanese word across every occurrence before adding a confirmation.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"\[(\d+)\]")

# Only context proposals that are currently strong enough to inspect.  The
# values are written as Unicode here because this is an analysis aid, not an
# input to the game's binary.
PROVISIONAL = {
    4: "手", 19: "前", 22: "川", 37: "沼", 38: "崎", 58: "言", 62: "成",
    63: "最", 91: "城", 119: "証", 129: "知", 169: "以", 176: "教",
    199: "印", 200: "象", 215: "関", 218: "引", 252: "縁", 256: "係",
    259: "動", 263: "企", 283: "間", 297: "承", 304: "可", 305: "能",
    314: "訪", 315: "何", 316: "度", 317: "利", 319: "植", 322: "料",
    335: "御", 338: "設", 342: "算", 343: "計", 350: "制", 360: "営",
    361: "活", 367: "常", 378: "撃", 401: "株", 404: "押", 407: "目",
    411: "声", 415: "新", 421: "顧", 423: "記", 424: "録", 428: "恋",
    429: "副", 432: "月", 433: "曜", 434: "金", 435: "幸", 436: "司",
    438: "致", 441: "等", 445: "慎", 446: "太", 447: "郎", 462: "吉",
    485: "二", 487: "輩", 492: "器", 502: "満", 503: "画", 518: "義",
    525: "枚", 526: "撮", 558: "屈", 559: "辱", 565: "乱", 566: "気",
    568: "土", 569: "座", 570: "全", 574: "清", 579: "影", 580: "響",
    596: "移", 601: "上", 602: "潔", 612: "功", 613: "績", 632: "再",
    651: "邪", 652: "魔", 662: "拘", 663: "留", 681: "源", 685: "駆",
    707: "捨", 721: "毎", 733: "験", 739: "関", 741: "卒", 747: "尊",
    748: "敬", 754: "粧", 768: "憶", 786: "香", 793: "術", 802: "看",
    811: "油", 819: "衣", 823: "状", 824: "況", 831: "豊", 832: "島",
    848: "論", 874: "混", 875: "晩", 889: "後", 944: "治", 945: "療",
    949: "因", 960: "管", 962: "布", 976: "振", 986: "秘", 989: "政",
    1002: "久", 1046: "候", 1047: "補", 1048: "太", 1054: "迷", 1055: "惑",
    1063: "文", 1064: "句", 1069: "七", 1070: "芝", 1078: "巻", 1082: "賛",
    1084: "悪", 1104: "授", 1110: "聴", 1116: "冗", 1117: "談", 1120: "停",
    1121: "材", 1131: "加", 1132: "珍", 1150: "懲", 1214: "惨", 1226: "胸",
    1248: "瀬", 1270: "虚", 1271: "腸", 1272: "炎", 1274: "繋", 1308: "層",
    1343: "頷", 1362: "嬉", 1366: "遂",
}


def load_mapping() -> dict[int, str]:
    entries = json.loads((ROOT / "font_extract" / "charmap_final.json").read_text(encoding="utf-8"))
    mapping = {int(item["index"]): item["char"] for item in entries}
    extra_path = ROOT / "font_extract" / "charmap_additional_confirmed.json"
    if extra_path.exists():
        extra = json.loads(extra_path.read_text(encoding="utf-8"))
        for item in extra.get("character_confirmations", []):
            indices = item.get("glyph_indices", [])
            confirmed = item.get("confirmed", "")
            if len(indices) == len(confirmed):
                mapping.update(zip(indices, confirmed))
    mapping.update(PROVISIONAL)
    return mapping


def decode(text: str, mapping: dict[int, str]) -> str:
    return TOKEN.sub(lambda m: mapping.get(int(m.group(1)), f"□{m.group(1)}□"), text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("indices", nargs="*", type=int)
    parser.add_argument("--orders", nargs="*", type=int, default=[])
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    wanted = set(args.indices)
    order_wanted = set(args.orders)
    mapping = load_mapping()
    raw_path = ROOT / "font_extract" / "script_full_raw.tsv"
    with raw_path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))

    for order, row in enumerate(rows):
        ids = {int(x) for x in TOKEN.findall(row["text"])}
        if (wanted and not wanted.intersection(ids)) and order not in order_wanted:
            continue
        if not wanted and order not in order_wanted:
            continue
        print(f"{order:5d} {row['offset']}  {decode(row['text'], mapping)}")
        if args.limit and order >= args.limit:
            pass


if __name__ == "__main__":
    main()

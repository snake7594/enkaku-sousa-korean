"""The Korean for the tutorial pages, with the box each block of type occupies.

Boxes are written out rather than detected.  Two passes at detection went wrong in opposite
directions -- counting colours per cell called anti-aliased type photographic and swallowed the
panel; counting colours over a block could not tell a small screenshot from a paragraph -- and
the pages carry gauges and icons that must not be cleared along with the text.  Twenty-one
pages is few enough to state exactly.

The panel is the same on every page: an orange border at (8,8)-(391,190), a heading bar down to
y=44, the page number in the bottom right.  Body text sits either beside a screenshot on the
left, from x=196, or across the full width from x=14.

Wording follows what the patch already uses elsewhere: クルー is 단서 (the released texture for
情報一覧 reads 단서 일람), 心証 is 심증, 黙秘権 is 묵비권.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")

HEAD = [12, 14, 280, 39]
WIDE = 14
BESIDE = 196
RIGHT = 385

# id -> (heading, [(box, korean), ...])
PAGES = {
    "0001_046b000_2": ("정보 집약에 관하여", [
        ((BESIDE, 52, RIGHT, 170),
         "특정 단서가 모이면\n정보 집약이 발생합니다.\n단서를 조합하면 새로운\n정보나 단서를 얻을 수\n있습니다."),
    ]),
    "0001_0470800_2": ("정보 집약에 관하여", [
        ((BESIDE, 52, RIGHT, 100),
         "정보 집약으로 얻은 단서는\n주황색 카드로 표시됩니다."),
        ((WIDE + 6, 110, RIGHT, 168),
         "조합에 실패해도 벌점은 없으며,\n몇 번이든 다시 시도할 수 있습니다.\n추리력을 발휘해 올바른 조합을 찾으십시오."),
    ]),
    "0001_0475000_2": ("심문에 관하여", [
        ((WIDE, 50, RIGHT, 74), "이제부터 미우라 형사의 심문이 시작됩니다."),
        ((BESIDE, 96, RIGHT, 162),
         "미우라 형사가 들이대는\n심문에 단서를 골라\n답변하십시오."),
    ]),
    "0001_0479800_2": ("심문에 관하여", [
        ((WIDE, 52, RIGHT, 92),
         "심문에 어떻게 답하느냐에 따라 미우라 형사의\n『심증』이 변합니다. 심증은 게이지로 표시됩니다."),
    ]),
    "0001_047e800_2": ("심문에 관하여", [
        ((WIDE, 52, RIGHT, 104),
         "미우라 형사의 심문에 증거가 되는 단서를 들이대어\n자신의 주장이나 알리바이를 입증하면\n심증 게이지가 올라갑니다."),
    ]),
    "0001_0483800_2": ("심문에 관하여", [
        ((WIDE, 52, RIGHT, 104),
         "근거 있는 답변을 하지 못하면 심증 게이지가\n줄어듭니다. 심증이 나빠지면 송치·기소되어\n게임 오버가 됩니다."),
    ]),
    "0001_0488800_2": ("심문에 관하여", [
        ((BESIDE, 52, RIGHT, 168),
         "사실을 증명할 단서가\n아직 모이지 않았거나\n답변에 자신이 없을 때는\n『묵비권』을 고르십시오.\n※묵비권은 빨간 카드로 표시됩니다."),
    ]),
    "0001_048d000_2": ("심문에 관하여", [
        ((WIDE, 52, RIGHT, 150),
         "『묵비권』을 골라도 심증 게이지는\n줄어들지만, 답변에 실패했을 때보다\n줄어드는 폭이 작습니다.\n\n또한 고른 단서에 따라서는\n심증 게이지가 오르내리지 않기도 합니다."),
    ]),
    "0001_0493800_2": ("조사에 관하여", [
        ((BESIDE, 52, RIGHT, 170),
         "여기서부터는 노리코의\n시점으로 조사합니다.\n\n조사를 의뢰한 장소를\n자유롭게 돌아다니며\n원하는 곳을 조사할 수 있습니다."),
    ]),
    "0001_0499800_2": ("조사에 관하여", [
        ((BESIDE, 52, RIGHT, 170),
         "방향키나 아날로그 패드로\n커서를 움직일 수 있습니다.\n\n커서가 바뀐 상태에서\n○ 버튼을 누르면 대화나\n조사 같은 행동을 합니다."),
    ]),
    "0001_04a2000_2": ("조사에 관하여", [
        ((BESIDE, 52, RIGHT, 170),
         "조사를 끝낼 때는 「뒤로」를\n골라 조사 종료 선택지를\n띄웁니다.\n\n장소에 따라서는 입구까지\n가야 조사를 끝낼 수 있습니다."),
    ]),
    "0001_04a7800_2": ("조사 의뢰에 관하여", [
        ((BESIDE, 52, RIGHT, 170),
         "변호사에게 조사를 의뢰합니다.\n\n조사를 의뢰할 장소를\n오전, 오후 순서로\n두 곳 고르십시오."),
    ]),
    "0001_04ad000_2": ("조사 의뢰에 관하여", [
        ((BESIDE, 52, RIGHT, 170),
         "조사를 의뢰하는 시간과\n요일은 매우 중요합니다.\n\n조사 장소에는 「휴무일」과\n「부재 시간」이 있어,\n그때는 조사할 수 없습니다."),
    ]),
    "0001_04b4000_2": ("조사 의뢰에 관하여", [
        ((BESIDE, 52, RIGHT, 170),
         "휴무일 정보는 주로\n조사 장소에 있는 인물과의\n대화에서 얻을 수 있습니다.\n\n정보를 놓치지 않도록\n주의하십시오."),
    ]),
    "0001_04ba000_2": ("조사 의뢰에 관하여", [
        ((WIDE + 20, 56, RIGHT, 136),
         "구류 기간은 최대 23일이므로\n조사할 수 있는 날수는 한정돼 있습니다.\n\n각 장소의 특성을 파악해\n효율적으로 조사하십시오."),
    ]),
    "0001_04bd800_2": ("사전에 관하여", [
        ((BESIDE - 76, 52, RIGHT, 168),
         "사전은 게임에 나오는 전문 용어나\n속어 등을 찾아볼 수 있는 기능입니다.\n\n대화 중 글자가 초록색으로 표시될 때\n□ 버튼을 누르면 단어를\n고를 수 있게 됩니다."),
    ]),
    "0001_04c3000_2": ("사전에 관하여", [
        ((BESIDE, 52, RIGHT, 168),
         "문장에 단어가 여럿 있을\n때는 □ 버튼으로 찾아볼\n단어를 고를 수 있습니다.\n\n단어를 고른 상태에서\n○ 버튼을 누르면\n사전 화면이 열립니다."),
    ]),
    "0001_04c8000_2": ("사전에 관하여", [
        ((BESIDE - 40, 52, RIGHT, 168),
         "사전 보기를 끝낼 때는\n× 버튼으로 대화 화면까지 돌아갑니다.\n\n본 적이 있는 사전·해설은\n메뉴의 「사전·해설」에서\n언제든 확인할 수 있습니다."),
    ]),
    "0001_04cd000_2": ("단서에 관하여", [
        ((BESIDE - 60, 52, RIGHT, 168),
         "대화나 조사로 얻는 정보는\n단서로 쌓입니다.\n\n단서는 사건의 수수께끼를 푸는\n실마리이며, 심문의 답변이나\n대화 등에 쓸 수 있습니다."),
    ]),
    "0001_04d1800_2": ("단서에 관하여", [
        ((BESIDE, 52, RIGHT, 140),
         "얻은 단서의 자세한 내용은\n메뉴의 「정보 일람」에서\n확인할 수 있습니다."),
    ]),
    "0001_04d5800_2": ("단서에 관하여", [
        ((BESIDE - 30, 52, RIGHT, 168),
         "정보 일람에서는 단서의\n입수 상황에 따라 아이콘이\n표시됩니다.\n\n新: 새로 얻은 단서\n更: 내용이 갱신된 단서\n※아이콘은 이틀 뒤에 사라집니다."),
    ]),
}


# Boxes measured off the pages, not guessed: for each block of type, the rows its ink actually
# occupies within the column it sits in.  The first attempt used round numbers and cleared only
# the top line or two of a paragraph, leaving the rest of the Japanese showing under the Korean.
# Bottoms stay above y=176 so the page number in the corner survives, and above the gauges on
# the pages that have them.
BOXES = {
    "0001_046b000_2": [(196, 66, 385, 165)],
    "0001_0470800_2": [(196, 60, 385, 98), (20, 120, 385, 175)],
    "0001_0475000_2": [(14, 55, 385, 76), (196, 101, 385, 158)],
    "0001_0479800_2": [(14, 63, 385, 103)],
    "0001_047e800_2": [(14, 66, 385, 123)],
    "0001_0483800_2": [(14, 66, 385, 123)],
    "0001_0488800_2": [(166, 71, 385, 164)],
    "0001_048d000_2": [(14, 59, 385, 171)],
    "0001_0493800_2": [(196, 56, 385, 167)],
    "0001_0499800_2": [(166, 56, 385, 170)],
    "0001_04a2000_2": [(118, 66, 385, 160)],
    "0001_04a7800_2": [(196, 68, 385, 162)],
    "0001_04ad000_2": [(182, 50, 385, 174)],
    "0001_04b4000_2": [(196, 57, 385, 168)],
    "0001_04ba000_2": [(34, 67, 385, 160)],
    "0001_04bd800_2": [(120, 58, 385, 169)],
    "0001_04c3000_2": [(196, 50, 385, 174)],
    "0001_04c8000_2": [(156, 59, 385, 170)],
    "0001_04cd000_2": [(136, 61, 385, 172)],
    "0001_04d1800_2": [(196, 85, 385, 142)],
    "0001_04d5800_2": [(148, 54, 385, 174)],
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--survey", type=Path, default=ROOT / "build" / "container_text.json")
    parser.add_argument("--banners", type=Path, default=ROOT / "work" / "container_ko_draft.json")
    parser.add_argument("--out", type=Path, default=ROOT / "work" / "container_ko.json")
    args = parser.parse_args()

    survey = {i["id"]: i for i in
              json.loads(args.survey.read_text(encoding="utf-8"))["images"]}
    entries = list(json.loads(args.banners.read_text(encoding="utf-8"))["images"])

    missing = [k for k in PAGES if k not in survey]
    if missing:
        raise SystemExit(f"not in the patchable set: {missing}")

    for page_id, (heading, blocks) in PAGES.items():
        item = survey[page_id]
        labels = [{"box": HEAD, "ja": "", "ko": heading, "font": "gothic",
                   "colour": "#ffffff", "size": 26}]
        for (_, korean), box in zip(blocks, BOXES[page_id]):
            labels.append({"box": list(box), "ja": "", "ko": korean,
                           "font": "gothic-light", "colour": "#f0f0f0", "size": 17})
        entries.append({"id": page_id, "block": item["block"], "record": item["record"],
                        "labels": labels})

    args.out.write_text(json.dumps({"schema": "enkaku_container_ko_v1", "images": entries},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(entries)} pictures ({len(PAGES)} tutorial pages) -> {args.out}")


if __name__ == "__main__":
    main()

"""Normalize the translated script before the runtime reflow pass.

The translation ledger is a TSV, but a few entries were written with physical
newlines in the text column. A normal splitlines() pass consequently drops the
continuation lines. This module treats every 0x... line as a new record, folds
continuation lines back into the text, applies the last contextual fixes, and
keeps dialogue/narration inside a conservative display width.

The output still uses literal "\\n" escapes in the TSV, so it remains easy to
inspect and safe for tools that expect one logical record per physical line.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


DEFAULT_MAX_DIALOGUE_WIDTH = 19
RESIDUAL_RE = re.compile(
    r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]"
)


# These rows were the remaining Japanese/CJK-bearing translations after the
# previous context and charmap passes. They are kept here as an explicit,
# reproducible decision log rather than being silently altered by a broad
# character substitution.
RESIDUAL_OVERRIDES: dict[str, str] = {
    "0x0006a612": "【도요시마】\n사이토는 활발하고 시원시원한 여자아이였습니다.\n남자아이 못지않은 행동력으로,\n부를 거침없이 이끌었지요.",
    "0x0006dc1b": "【마스터】\n그녀에게 도움이 된다면,\n얼마든지 해드리죠.",
    "0x0007337a": "【코우지】\n그렇지.\n총성이 들린 시간, 즉 0시 44분이\n범행 시각이라고 생각하게 하려는 거야.",
    "0x00077da3": "【종업원】\n그건 아니에요.\n이 플레이어는\n두 종류의 흔적에 대응하니까요.",
    "0x00087758": "【신타로】\n그 사람들 이야기는, 미즈타니 씨가 더 자세히 알 거야.\n그녀에게 물어보면 돼.",
    "0x0008a3ee": "【신지】\n그녀는 때로는 나를 아들처럼 아껴 주었고,\n때로는 호되게 꾸짖어 주었습니다.",
    "0x0008a464": "【신지】\n그녀에게 마음을 품기까지,\n그렇게 오래 걸리지는 않았습니다.",
    "0x0008a507": "【신지】\n그녀가 졸업하고 결혼한 뒤에도,\n저는 계속 그녀를 그리워했습니다.\n그녀의 상황이 늘 마음에 걸렸습니다.",
    "0x0008a82f": "【신지】\n그녀에게는 이미 아이가 있었습니다.\n그래서 저는 그녀에게 생활비 지원을 제안했습니다.\n솔직하게 프러포즈도 했습니다.",
    "0x0008aa19": "【신지】\n좀 더 솔직하게 말했다면,\n그녀를 슬프게 하지 않아도 됐을 텐데……",
    "0x0008ac5a": "【신지】\n그녀가 싫은 건 아닙니다.\n하지만 제 마음속에는 아직 카츠요 씨가……",
    "0x0008af65": "【신타로】\n그 시간을 만들기 위해 수술하는 거야!\n그녀를 위해서라도 반드시 수술을 성공시키고\n돌아오겠다!!",
    "0x0009a72f": "【교원】\n레버 상태가 나빠져 버려서,\n수리했어요……",
    "0x0009d412": "【노리코】\n알겠어.\n명함을 받았던 시기를\n조사하고 싶은 거지.",
    "0x0009e8a9": "【코우지】\n1층 가장 안쪽에 집주인 아저씨가 살고 있으니까\n거기서 열쇠를 빌릴 수 있을 거야.",
    "0x000ab5e6": "【코우지】\n원제, 다음 주 아침부터 다시 일하게 됐대.",
    "0x000b63e3": "【신타로】\n그것이 원인이 되어\n시라카와 이치로가 그녀를 책망하다\n자살해 버렸어……",
    "0x000b644a": "【신타로】\n그녀의 자살은,\n전부 내 책임이야……",
    "0x000b6606": "【신타로】\n아니, 그건 그냥 단정일 뿐이야.\n그녀의 뒤를 쫓아갈 만큼의 용기도\n내게는 없었어……",
    "0x000c1306": "【신타로】\n마스터에게 열쇠를 빌려서 가져온 거겠지.\n그녀 사정도 있었고,\n그렇게 시간을 낭비하진 않았을 거야.",
    "0x000c2687": "【미우라】\n여기가 지금 우리가 있는 홀이야.\n너와 미즈타니 아사츠유는 이 카운터에서\n시간을 때우고 있었고……\n그건 틀림없지?",
    "0x000c641a": "【콘도】\n뭐야, 그 도전적인 눈은?\n경찰을 너무 무시하지 마, 이 자식아!",
    "0x000cdc29": "【미우라】\n기일은 내일이다.\n내일까지 모든 심문에 대해\n반론하지 못하면\n형사소송 절차에 들어가게 해주지.",
    "0x000dad9a": "【코우지】\n하지만 “하지 않았다”는 걸 증명하려면\n“했다”는 모든 가능성을\n부정하는 수밖에 없어!",
    "0x000daea3": "【미우라】\n그 말이 맞다.\n그러니 충고했잖아?\n술에 취해 기억이 없다는 네 주장이 널 괴롭힌다고.",
    "0x000dd12d": "【코우지】\n(한순간, 요시모토 형사에게 휘둘렸던……\n대단한 사람이네, 그 사람……)",
    "0x000e64f9": "【요시모토】\n저는 그녀처럼\n교섭술에 능하지 않으므로,\n당신의 자백을 기다리는 것 외에는\n아무것도 할 생각이 없습니다.",
    "0x000e8c86": "【코우지】\n아깝다.\n이런 식으로 말하면 또 화낼지도 모르지만,\n당신은 아사츠유 씨의 딸이겠지?",
    "0x000f0e38": "【미우라】\n콘도 카츠미.\n수뢰죄 혐의로 긴급 체포한다.",
    "0x000f518a": "【미우라】\n이제 와서 얼버무리며,\n엉터리 답변을 바꾸는 건 그만둬!\n이건 너를 위한 말이다!",
    "0x000f9d91": "【미우라】\n그녀의 행동은,\n화장을 고치고 있던 것으로 추정하자.",
    "0x000fbb29": "【코우지】\n그녀는 요시모토 유미.\n아사츠유 씨의 딸이야.",
    "0x000ff49d": "【코우지】\n(그녀는 살해당한 시라카와 이치로의 딸,\n시라카와 노조미야!)",
    "0x00106787": "【아사츠유】\n어머, 괜찮아요!\n좋은 신랑감은 많이 알고 있으니까요.",
    "0x0011226a": "【신타로】\n그것뿐만이 아니야!\n기억나?\n가세 교수의 가발 분실 사건 때도……",
    "0x00112371": "【신타로】\n그때도 내가 범인으로 몰렸잖아.",
    "0x0011348d": "【신타로】\n노리코 씨의 말이야.\n그녀는 아직 신참 변호사지만,\n사무소 안에서의 평가는 높아.",
    "0x00113525": "【신타로】\n그녀의 재능을 일찌감치 알아보고\n아버지에게 소개한 건 나니까.\n나도 자부심이 높지…… 아하하.",
    "0x001137af": "【신타로】\n그래.\n아빠라고 부르고 있어.\n그녀는 장차 우리 사무소를 물려받아도\n이상하지 않을 인재야.",
    "0x0011382b": "【코우지】\n토요코를 내버려 두고?",
    "0x00113d3d": "【신타로】\n그런,\n표면화해서는 안 되는 사건을\n뒤에서 정리하는 교섭술에는\n매우 고도의 기술이 필요하게 된다.",
    "0x00113dc5": "【신타로】\n한편으로, 그런 위험한 교섭술을\n성공시키면, 그건 신뢰가 되어\n업계에까지 이름이 알려지게 된다.",
    "0x0011811f": "【코우지】\n아오이의 오빠 이름은,\n『코우지』……라고 하는 건가?",
    "0x0011e968": "【노조미】\n아시로 아주머니와 결혼한 것도,\n사회적 입장을 고려한 일이라고\n삐딱하게 생각했던 때도 있었습니다.",
    "0x0012390e": "【노조미】\n그녀는 어린 저를 배려해,\n계속 비밀로 하고 있었던 모양입니다.",
    "0x001241d6": "【코우지】\n……그런 애정이 부족했던 사람이\n일과 사생활을\n그렇게 깔끔하게 분리할 수 있을까?",
    "0x00124b9d": "【코우지】\n(배신당한 이치로가\n재혼을 결심하게 된 경위는\n조금 수상하다……)",
    "0x00125154": "【아사츠유】\n뭐, 어쩔 수 없잖아?\n살인 사건의 구류 중이니까,\n그렇지 않다고.",
    "0x0012cb5d": "【나나시바】\n이대로라면 또 다음 주 일요일이\n힘들어지겠지?",
    "0x00132fed": "【코우지】\n언제나,\n『코우지 형!\n같이 목욕탕에 들어가!』\n라는 느낌인데.",
    "0x001338ed": "【나나시바】\n……그래.\n맞아.\n그럼, 코우지에게 개요만.",
    "0x001343f9": "【코우지】\n그렇게 목욕탕에 자주 들어가진 않았지만,\n가끔 밖에 못 나가게 되면,\n그 고마움을 알게 되지.",
    "0x00136f71": "\n　\n과연,\n어떤 사람일까?",
    "0x001399e6": "\n\n미나즈키는 피해자와 궁합이 나빴던 것 같지만,\n미나즈키가 복직할 시기에 맞춰 벌어진 살인 사건.\n단순한 우연으로 치부해도 좋은 것일까……?",
    "0x0013a3f9": "\n　\n불법에 가까운 조사를 하기 위해\n준비물을 마련해 뒀다는 건가.\n역시라고 해야 할까, 뭐라고 할까……",
    "0x0013a58d": "\n　\n아사츠유 씨의 본명은 요시모토 스미카이고,\n시라카와 신지와의 사이에\n요시모토 유미라는 딸이 있다.",
    "0x0013e60b": "\n　\n시라카와 이치로는 그다지 강하지 않다.\n시대가 되었다고 할 정도는 아니지만,\n유리잔으로 2~3잔만 마셔도,\n금세 취해 버린다.",
    "0x0013e678": "\n　\n하지만 사람과 어울리는 건 싫어하지 않는다.\n이날은 축하할 일도 있었으니,\n평소의 열 배는 마셨을 것이다.\n마지막 술자리에 도착했을 때는,\n현실과 망상을 오가며\n살고 있었다.",
    "0x00142f0e": "【코우지】\n아, 기억해.\n끔찍한 이야기였지.\n대체로, 내가 가세 교수의 가발을 망가뜨려서\n무슨 이득이 있다는 거야.",
    "0x0014313d": "【코우지】\n흠, 옛날 일이네……\n살인 사건과 가발 분실 사건은\n같은 수준이 아닐 것 같다!?",
    "0x0014d144": "【아사츠유】\n으으으으으으윽!!",
    "0x0014ec6d": "【이치로】\n으으으으윽!!",
    "0x0014f046": "【이치로】\n키, 키사마아아아아아……\n이럴 때에 으으으으으……!!",
    "0x0014f6af": "【이치로】\n그아아아아아~~~~~\n~~~~~~~~~~~~~\n~~~~~~~~~~~~~\n~~~~~~~~아아!!!",
    "0x00156df5": "【아사츠유】\n속으로는 슬픔에 무너질 것 같았어……\n몇 번이나 계획을 중단하려고\n생각했는지……",
    "0x00157f4c": "【코우지】\n시라카와 이치로의 딸, 기억하시죠?\n그녀가 아사츠유 씨에게 전해 달라고 했어요.",
    "0x001581ab": "【아사츠유】\n그녀에게도 고맙다고 전해 두고……\n……언젠가 이야기를 나누러 갈 테니까……",
}


SEMANTIC_OVERRIDES_PATH = (
    Path(__file__).resolve().parents[1]
    / "font_extract"
    / "translation_semantic_overrides.json"
)


def load_semantic_overrides() -> dict[str, dict[str, str]]:
    """Load the reviewed source-conditioned translation decisions."""
    if not SEMANTIC_OVERRIDES_PATH.exists():
        return {}
    payload = json.loads(SEMANTIC_OVERRIDES_PATH.read_text(encoding="utf-8"))
    overrides: dict[str, dict[str, str]] = {}
    for item in payload.get("overrides", []):
        offset = item["offset"]
        if offset in overrides:
            raise ValueError(f"duplicate semantic override offset: {offset}")
        overrides[offset] = item
    return overrides


SEMANTIC_OVERRIDES = load_semantic_overrides()


def parse_loose_tsv(path: Path) -> tuple[str, list[list[str]]]:
    """Read one logical row even when a text field contains physical newlines."""
    physical = path.read_text(encoding="utf-8").splitlines()
    if not physical:
        raise ValueError(f"empty translation file: {path}")
    header = physical[0]
    rows: list[list[str]] = []
    current: list[str] | None = None
    for line in physical[1:]:
        if line.startswith("0x"):
            if current is not None:
                rows.append(current)
            parts = line.split("\t", 2)
            if len(parts) < 3:
                raise ValueError(f"malformed translation row: {line!r}")
            current = [parts[0], parts[1], parts[2]]
        elif current is not None:
            current[2] += r"\n" + line
        elif line.strip():
            raise ValueError(f"orphan continuation line: {line!r}")
    if current is not None:
        rows.append(current)
    return header, rows


def is_story_text(text: str, include_fullwidth_choices: bool = False) -> bool:
    if text.startswith(("\n", r"\n")):
        return True
    stripped = text.lstrip()
    prefixes = ("【", "[", "［") if include_fullwidth_choices else ("【", "[")
    return stripped.startswith(prefixes)


def wrap_line(line: str, width: int) -> list[str]:
    """Wrap one visible line, preferring a Korean word boundary."""
    if len(line) <= width:
        return [line]
    result: list[str] = []
    remaining = line
    while len(remaining) > width:
        cut = remaining.rfind(" ", 0, width + 1)
        if cut <= 0:
            cut = width
            result.append(remaining[:cut])
            remaining = remaining[cut:]
        else:
            result.append(remaining[:cut].rstrip())
            remaining = remaining[cut + 1:].lstrip()
    result.append(remaining)
    return result


def fit_story_text(text: str, width: int = DEFAULT_MAX_DIALOGUE_WIDTH,
                   include_fullwidth_choices: bool = False) -> str:
    """Keep explicit breaks and add only the breaks needed by long story lines."""
    if not is_story_text(text, include_fullwidth_choices):
        return text
    visible_lines = text.replace(r"\n", "\n").split("\n")
    wrapped: list[str] = []
    for line in visible_lines:
        # A speaker tag is a separate line in every dialogue row. Treating it
        # as ordinary prose could split a name from its closing bracket.
        if line.startswith("【") and line.endswith("】"):
            wrapped.append(line)
        else:
            wrapped.extend(wrap_line(line, width))
    return "\n".join(wrapped).replace("\n", r"\n")


def normalized_rows(path: Path, width: int = DEFAULT_MAX_DIALOGUE_WIDTH,
                    apply_overrides: bool = True
                    ) -> tuple[str, list[list[str]], dict]:
    header, rows = parse_loose_tsv(path)
    source_offsets = {row[0] for row in rows}
    if apply_overrides:
        missing = sorted(set(RESIDUAL_OVERRIDES) - source_offsets)
        if missing:
            raise ValueError(f"override offsets missing from translation: {missing}")
        missing_semantic = sorted(set(SEMANTIC_OVERRIDES) - source_offsets)
        if missing_semantic:
            raise ValueError(
                "semantic override offsets missing from translation: "
                f"{missing_semantic}"
            )

    override_count = 0
    semantic_override_count = 0
    wrapped_count = 0
    output: list[list[str]] = []
    for offset, _line_count, text in rows:
        if apply_overrides and offset in RESIDUAL_OVERRIDES:
            text = RESIDUAL_OVERRIDES[offset]
            override_count += 1
        if apply_overrides and offset in SEMANTIC_OVERRIDES:
            text = SEMANTIC_OVERRIDES[offset]["korean"]
            semantic_override_count += 1
        fitted = fit_story_text(
            text,
            width,
            include_fullwidth_choices=not apply_overrides,
        )
        if fitted != text:
            wrapped_count += 1
        line_count = fitted.count(r"\n") + 1
        output.append([offset, str(line_count), fitted])

    residuals = [
        row[0] for row in output
        if RESIDUAL_RE.search(row[2].replace(r"\n", ""))
    ]
    physical_lines = path.read_text(encoding="utf-8").splitlines()
    report = {
        "logical_rows": len(output),
        "physical_rows": len(physical_lines) - 1,
        "residual_overrides": override_count,
        "semantic_overrides": semantic_override_count,
        "semantic_override_path": str(SEMANTIC_OVERRIDES_PATH),
        "applied_preexisting_overrides": apply_overrides,
        "wrapped_story_rows": wrapped_count,
        "max_dialogue_width": width,
        "japanese_or_cjk_residual_rows": residuals,
        "malformed_physical_continuations": sum(
            1 for line in physical_lines[1:]
            if line and not line.startswith("0x")
        ),
    }
    return header, output, report


def write_normalized(path: Path, output: Path,
                     width: int = DEFAULT_MAX_DIALOGUE_WIDTH,
                     apply_overrides: bool = True) -> dict:
    header, rows, report = normalized_rows(path, width, apply_overrides)
    if report["japanese_or_cjk_residual_rows"]:
        raise ValueError(
            "Japanese/CJK remains after cleanup: "
            + ", ".join(report["japanese_or_cjk_residual_rows"])
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(header + "\n")
        for offset, line_count, text in rows:
            stream.write(f"{offset}\t{line_count}\t{text}\n")
    return report


def load_for_patch(path: Path, width: int = DEFAULT_MAX_DIALOGUE_WIDTH,
                   apply_overrides: bool = True
                   ) -> list[tuple[int, str]]:
    """Return normalized offsets/text for build_patch without a second TSV."""
    _, rows, report = normalized_rows(path, width, apply_overrides)
    if report["japanese_or_cjk_residual_rows"]:
        raise ValueError(
            "Japanese/CJK remains after cleanup: "
            + ", ".join(report["japanese_or_cjk_residual_rows"])
        )
    return [(int(offset, 16), text) for offset, _, text in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--width", type=int, default=DEFAULT_MAX_DIALOGUE_WIDTH)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument(
        "--final-input",
        action="store_true",
        help="the input already contains all reviewed overrides; only fold and wrap it",
    )
    args = parser.parse_args()

    report = write_normalized(
        args.source, args.out, args.width, apply_overrides=not args.final_input
    )
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"-> {args.out}")
    if args.report:
        print(f"-> {args.report}")


if __name__ == "__main__":
    main()

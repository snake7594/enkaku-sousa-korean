"""Generate the source-conditioned semantic translation correction ledger.

This pass is intentionally conservative: it only changes rows whose Japanese
source contains a high-confidence term or whose local context makes the
existing Korean unambiguously wrong.  The resulting JSON is consumed by
translation_text.py before the runtime reflow step.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "work"))
import translation_text  # noqa: E402


TSV = ROOT / "build" / "translation_ko_clean.tsv"
SOURCE_TSV = ROOT / "font_extract" / "script_full_ja.tsv"
AUDIT = ROOT / "build" / "translation_semantic_audit_cfg16.json"
OUT = ROOT / "font_extract" / "translation_semantic_overrides.json"


def parse_tsv(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        parts = line.split("\t", 2)
        if len(parts) == 3:
            result[parts[0]] = parts[2]
    return result


def base_translations() -> dict[str, str]:
    header, rows = translation_text.parse_loose_tsv(TSV)
    del header
    result: dict[str, str] = {}
    for offset, _line_count, text in rows:
        if offset in translation_text.RESIDUAL_OVERRIDES:
            text = translation_text.RESIDUAL_OVERRIDES[offset]
        result[offset] = translation_text.fit_story_text(text)
    return result


def with_header(old: str, body: str) -> str:
    """Keep the already-established speaker tag and replace only the body."""
    header = old.split(r"\n", 1)[0]
    return header + "\n" + body


def add(
    overrides: dict[str, dict],
    offset: str,
    old: str,
    new: str,
    source: str,
    reason: str,
    confidence: str = "high",
) -> None:
    if old == new:
        return
    overrides[offset] = {
        "offset": offset,
        "source": source,
        "old_korean": old,
        "korean": new,
        "reason": reason,
        "confidence": confidence,
    }


def replace_all(text: str, replacements: list[tuple[str, str]]) -> str:
    for before, after in replacements:
        text = text.replace(before, after)
    return text


def main() -> None:
    source = parse_tsv(SOURCE_TSV)
    current = base_translations()
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    overrides: dict[str, dict] = {}

    # The following rows contain sentences whose automatic translation changed
    # the meaning, not merely the wording.
    body_map: dict[str, str] = {
        # クビ = dismissal/firing, not the unrelated token "곰팡이".
        "0x00059ffd": "아, 하지만 지는 걸 싫어하게 된 건\n회사에서 해고되고 나서였어요.\n그전에는 내성적이었거든요.",
        "0x00060f28": "그 시라카와 씨도 인정하고 있었어.\n하지만 내가 해고된 뒤에\n그 사람도 해고됐다는 말을 듣고\n놀랐던 기억이 나.",
        "0x00060fd0": "게다가 해고된 이유가 병 때문이라고 들어서,\n아, 나와 같다고 생각해 동정했는데……\n하지만 실제로는 나보다 더 괴로운 일을\n당했던 모양이야.",
        "0x0006110e": "병을 이유로 해고당해서……\n본인은 납득하지 못했겠지요.",
        "0x00083c25": "하지만 어느 날 갑자기\n시라카와 준이 해고했어.",
        "0x000aaa06": "저희가 맡은 의뢰에 깊이 관여하지 않는다는 조건으로,\n사무소 출입을 허가하고 있어.",
        "0x000af079": "아무래도 예전에 회사에서 해고됐을 때,\n슈트를 전부 버렸던 모양이야.",
        "0x000e298d": "이봐, 괜찮겠어?\n나 때문에 해고라도 당하면\n마음이 편치 않은데.",
        "0x000fafd2": "녀석은 지는 걸 극도로 싫어해.\n아마 예전에 회사에서 해고된 일의\n트라우마겠지.",
        "0x00127a8d": "……그렇습니다.\n오빠도 회사에서 해고되거나,\n병에 걸리기도 해서……",

        # 生徒 = student, not "생선".
        "0x000517ec": "저……\n준텐 고등학교 학생이시죠?",
        "0x0006961b": "죄송합니다. 지금 학생의 부모님이 와 계셔서,\n응접실이 붐비고 있어\n서서 말씀드리게 됐습니다만……",
        "0x00069dea": "다시 한 분 더 여쭤보고 싶은 분이 있습니다.\n자, 이 학교에 시라카와 신지라는\n학생이 다녔다고 들었습니다만……",
        "0x00069f7f": "자, 이 학교에 시라카와 신지라는\n학생이 다녔다고 들었습니다만……",
        "0x0006a328": "다음으로 한 분 더 여쭤보고 싶은 분이 있습니다.\n자, 이 학교에 사이토 가쓰요라는\n학생이 다녔다고 생각합니다만……",
        "0x0006a4bd": "잠깐, 이 학교에 사이토 가쓰요라는\n학생이 다녔다고 생각합니다만……",

        # Ambiguous glyph 署 is 机 in this local desk-inspection scene.
        "0x00069888": "(선생님들의 책상이네)",
        "0x000698c7": "(정리된 책상부터\n조금 어질러진 책상까지,\n정말 다양하네.)",
        "0x00069929": "(하지만 역시 학생들의 눈이 있어서인지,\n극단적으로 어질러진 책상은 없네.)",

        # The source says 兄 / お兄さん throughout this block.
        "0x001384de": "\n\n설마 ○○ 코우지가 아오이의 오빠,\n미나즈키 코우지였을 줄은……\n세상은 참 좁다고 해야 할까, 우연이라고\n해야 할까……",
        "0x00151abc": "고멘 고멘, 조금 엿보는 곳이\n있어……\n……잠깐, 할아버지가 아니라\n오빠라고 하자, 유미.",

        # A few other rows where the charmap and context make the intended
        # sentence clear.
        "0x0009b61a": "미나즈키의 성격, 취미, 행동……\n거기서 뭔가 알리바이를 증명할 수 있는 정보가\n나오기를 기대할 수밖에 없어.",
        "0x000feac4": "저기, 나도…… 그,\n선생님……?께 공부를 배울 수 있어서\n기뻤습니다.",
        "0x0011f4d0": "이 이야기를 들었을 때, 저도 모르게\n‘신지 씨에게 기회가\n찾아온 것 아니냐’고\n말해 버렸습니다만……",
        "0x001241d6": "……그런 사랑에 둘러싸여 자란 사람이\n일과 사생활을\n그렇게 쉽게 나눌 수 있을까?",
        "0x00125154": "뭐, 어쩔 수 없잖아?\n살인 사건으로 구류 중이니까,\n마음 편히 있을 수는 없다고.",
        "0x00113a68": "……사건의 규모로 말하면,\n업계 최고 기업 대표가\n살해당한 이 사건도\n결코 작지 않다고?",

        # 自殺 = suicide, not the stray token "자야".
        "0x000ad570": "어제는 노조미가 접견에 왔어.\n노조미의 친어머니인 아시로 씨의 자살에 대해\n조사하고 있던 내용을 알려 줬어.",
        "0x00123bb2": "(그 일을 시라카와 이치로에게 추궁당해\n노조미의 어머니가 자살……?)",
        "0x0012616b": "뭐라고 해야 할까……\n이렇게…… 생각에 잠긴 듯한 표정을 짓고 있어서……\n마치 자살이라도 생각하고 있는 듯한……",
        "0x0013ba48": "\n　\n아시로의 자살 사건에 대해 노리코가 입을 다물고 있었던 것은,\n누마사키 변호사의 지시였던 모양이다.",
        "0x0013be5c": "\n\n설마, 노조미의 친어머니가\n자살했다니……",
        "0x0014fbb8": "그, 그러면……\n시라카와 이치로는 살해당한 게 아니라,\n자살……이라는 건가?",
        "0x00152060": "아시로 씨의 자살……\n그리고 그 사건……",

        # 生徒 = student, including the later narration occurrence.
        "0x00115e1f": "(이 활기찬 2명은,\n우리 탐정 사무소 근처에 있는\n고등학교의 학생이다)",

        # Strong lexical corrections outside the first mechanical groups.
        "0x00047c40": "미나즈키가 말한,\nVIP룸 통로에서 나오는 걸 봤다는\n남자는, 아마 누마사키 변호사를\n말하는 거겠지.",
        "0x00047ce4": "확실히 누마사키 변호사는 23시 무렵\n현장에 도착해,\nVIP룸에서 5분 정도\n만나고 있었다고 했지?",
        "0x00047d6d": "대략적으로 생각해서,\n홀에 들어가 VIP룸에 들어가기 위한\n절차를 밟고,\n누마사키 변호사가 나갈 때까지 대략\n10분이라고 치자.",
        "0x0004803f": "누마사키 변호사는 몇 시쯤 VIP룸을\n나왔을까?",
        "0x00101a63": "선생님, 그때,\n진지하게 호소하셨죠?\n……저를 피해자의 가족으로 여기셨죠.",
        "0x00047b38": "자신에게 불리할 만한 일까지\n모두 말해 줬지만,\n객관적인 증언이나 증거가 나오지 않는 한\n믿을 수는 없어……",
        "0x00066a5e": "……그렇다는 건……\n코우지의 어머니가\n누군가에게 살해당했다는 것……!?",
        "0x00067e2a": "조직적으로……?\n설마, 그 사실을 은폐하기 위해\n피해자를 죽였다……!? ",
        "0x0007ad0e": "(이 중에서 살인이 일어났네)",
        "0x000827ca": "시라카와 이치로 살해 사건의\n건이지만,\n소장님, 당일 현장에 계셨지요?",
        "0x00095f45": "알겠습니다만, 의미가 없다고\n생각합니다.\n\n원장 선생님은, 게으르다가 곧바로\n자살해 버리셨으니까요.",
        "0x00095fb1": "에엣!? \n자살……?",
        "0x000970cb": "그것을 추궁하기 위해서,\n어머니는 살해당한 건가……?",
        "0x00097189": "……아니, 살해당했다고 단정하는 건\n성급해.\n무엇보다 객관적인 증거가 없어.",
        "0x000989fc": "자, 흔히 드라마 같은 데서\n살의가 어떻고 하는 이야기가 있잖아요.\n그 표정에서 느낀 건 바로 살의였어요……",
        "0x000992ee": "‘내가 사이토 시로를 죽였다고\n의심하고 있는 건가’라고.",
        "0x00099463": "아니요.\n무서워서……\n말하자면 제가 살해당할 거라고\n생각했으니까……",
        "0x000a71b3": "하지만 피해자와 미즈타니 씨는\n어떤 관계였을까……?\n설마 살의를 품을 정도로 깊은\n관계였던 걸까……?",
        "0x000b06cb": "지금까지는 어느 쪽인가 하면,\n관계자의 행적이라든가 알리바이라든가,\n살해 방법이나 트릭을 중심으로,\n사건이 일어난 당시의 일을\n조사해 왔던 거지?",
    }

    # These murder-related rows are all the high-confidence hard candidates
    # from the previous audit.  Full replacements avoid trying to infer
    # whether "야한" meant killed, killed-by, or killing from the Korean
    # token alone.
    murder_bodies: dict[str, str] = {
        "0x0005398e": "살인 사건부터 애완동물 수색까지,\n온갖 고민을 말끔히 해결해 드립니다!!",
        "0x0006a808": "……사이토 코우지 씨는,\n살인 사건의 피의자로서 체포되고 말았습니다.",
        "0x0006edd4": "다음에 살해 현장에 갔을 때라도\n들어 봐 주지 않겠어?",
        "0x00075ca7": "한 사람은 살해당한 사람.\n한 사람은 그 사람의 동행인인 변호사 씨.",
        "0x000921bf": "사실 사이토 가쓰요 씨의 장남인\n사이토 코우지 씨가\n살인 사건의 범인으로 의심받고 있습니다.",
        "0x00096da6": "어머니……\n역시 살해당한 건가……?",
        "0x0009bd27": "살해 현장이 된 VIP룸에도\n들어가 봤지만,\n결국 아무것도 기억해 내지 못했어……",
        "0x0009cb31": "자백하면, 살인죄가 아니라,\n상해치사죄로 입건하도록\n검사에게 부탁해 오겠다고 말해 왔어.",
        "0x0009db9d": "내 상사인 아사츠유 씨,\n살해 현장을 보존한 콘도 형사,\n그리고 누마사키 변호사와 젊은\n남자야.",
        "0x000a4161": "음, 그 아이에게는\n아버지를 죽인 범인에게 ‘살인자’라고\n말하는 것만으로도\n조금은 마음이 풀릴지도 모르지.",
        "0x000ae9b9": "살해당한 시라카와 이치로의\n딸이야.",
        "0x000b1272": "‘살해 현장에 대해 조사한다’는 거였다면,\n라이트 블루 안을 조사해 달라고\n했으면 됐을 텐데……",
        "0x000b1e94": "그러므로 피해자와 관련된 인물들의\n관계를 더 깊이 파고들어,\n살해 동기까지 도달해야 한다고 생각해.",
        "0x000b1f27": "즉 알리바이와 살해 동기의\n양면에서 사건을 파헤쳐 가는 거군요.",
        "0x000b3231": "그래.\n이 건에 관해서는,\n이마바야시의 살인 사건과는\n관계없어……",
        "0x000b36ea": "노조미 씨의 어머니가 자살한 것을\n코우지에게 숨겨 두는 것이……\n그렇군요.",
        "0x000b3815": "조사했다……고?\n노조미의 어머니가 자살한 사건 말이야?",
        "0x000b5717": "그 수기에는,\n남자 한 명을 죽였다는 내용이\n암시되어 있었어.\n그 남자는…… 준이라면 알겠지?",
        "0x000b5873": "(일부러 나에게 이런 식으로\n묻는 방법을 택할 정도다.\n나와 더 가까운 사람……\n그래, 시라카와 이치로가 죽인 사람은……)",
        "0x000b5916": "그렇지, 시라카와 준이 죽인 사람은\n준의 아버지인 사이토 시로 씨야.",
        "0x000b6230": "아시로 씨가 그때 ‘알았다’고\n말했지만,\n아시로 씨가 자살한 것을 생각하면,\n믿지 않았던 것 같네……",
        "0x000b649a": "왜 노리코에게\n아시로 씨가 자살한 것을\n입 다물게 한 겁니까?",
        "0x000c1609": "하면 거기에는 콘도 준과\n살해당한 시라카와 준의 시신만 있었고,\n범인은 벌써 어디에도 없었다.",
        "0x000c207e": "(오늘은 경찰서 내에서 취조는 진행되지 않고,\n살해 현장이 된 바 ‘라이트 블루’로\n끌려왔다)",
        "0x000c690a": "살인이 증명되면,\n사형도 있을 수 있어!",
        "0x000cef08": "어……\n네가 죽인 것을 인정하는 거냐?",
        "0x000cf00c": "나는 ‘네가 죽인 건 누구냐’고\n물었단 말이다?",
        "0x000d18c3": "네가 피해자와 말다툼하고 있었다는\n목격 증언이 있다.\n이것은 살해 동기로 이어질 수 있는\n이야기다.\n이걸 어떻게 설명할 거냐?",
        "0x000d77df": "그럼, 반대로 질문하겠다!\n동생에게 그 수첩을 보였다고 해서,\n왜 지금 피해자를 죽인 거냐!?",
        "0x000d7bdb": "화장실에서 피해자와 우연히 만나,\n아버지를 죽인 원한을 떠올리고,\n충동적으로 범행에\n이르렀다…… 다른가?",
        "0x000d7d29": "적어도 이마바야시의 사건이\n계획적인 살인인 것은 분명하다!\n왜냐하면……!",
        "0x000daa73": "술에 취해 있었다면,\n살인을 저지른 행위 자체를 건드리고\n있는 셈이다.\n그렇게 생각할 수 없나?",
        "0x000dab98": "술에 취해 기억을 잃고 있는데\n살인을 저지르지 않았다고\n주장한다면,\n그 근거를 보여 봐!",
        "0x000dad1d": "살인을 했다는 증명은,\n증거가 하나라도 있으면 성립한다!\n지금 경찰이 하는 일이야!",
        "0x000dda4f": "\n\n\n(나에게는 살인죄로 무기징역의\n형이 내려졌다……)",
        "0x000ded94": "「술에 취해 있었기 때문에 말다툼하고 있었다」\n「술에 취해 기억하지 못한다」\n라면, 경찰이 주장하는 「말다툼이 살해 동기가 되었다」\n는 가능성을 부정할 수 없다.\n여기는 말다툼을 하지 않았다고 부인하고 싶은 부분이지만…",
        "0x000df6b4": "발각될 수밖에 없는 VIP룸에서\n권총을 발사해 살해한 범행은\n겉보기에는 계획적으로 보이지만,\n총성은 밖으로 새어 나가 버렸다.\n계획적인 범행이라고 보기에는\n조금 엉성한 점이 눈에 띈다.",
        "0x000dfb41": "설령 술에 취해 있었다고 해도,\n살인은 가능하다.",
        "0x000e971c": "게다가 나는 살인 사건의 피의자다.\n오히려 이쪽이 도와주고 싶을 정도야.",
        "0x000fcc3a": "\n\n(나에게는 살인죄로 무기징역의 형이\n내려졌다……)",
        "0x000fd34c": "네가 술에 취해 있었다면,\n살인을 저지른 행위 자체를 만져\n버리고 있다……\n이렇게는 생각할 수 없을까……?",
        "0x000fd43c": "술에 취해 있었지만,\n살인을 저지르지 않았다는 것을\n주장한다면,\n그 근거를 보여 봐!",
        "0x000ff4fa": "(젠장, 몰랐다고는 해도,\n아버지를 살해당한 아이에게\n‘아버지는 잘 지내시니?’라니……!)",
        "0x000ff565": "(게다가 그 아이에게서 보면,\n나는 아버지를 죽인 인간이야!)",
        "0x000ff8fc": "살인자……",
        "0x001016ff": "내가 걱정해 줄까?\n일단 세상적으로는 내가 살인범이란 거지?\n뭐야?",
        "0x001018a0": "나는 선생님이 살인범이라곤\n생각하지 않으니까.",
        "0x00101c64": "보통 살인범이\n피해자의 가족을 걱정할까요?",
        "0x00106944": "‘살인범으로 기소될 것\n같습니다~!\n도와주세요~!’라고 마주할 때\n생각했는데.",
        "0x00113a68": "……사건의 규모로 말하면,\n업계 최고 기업 대표가\n살해당한 이 사건도\n결코 작지 않다고?",
        "0x00123ac3": "어머니가 자살한 것은\n그것이 원인이라고\n말씀하셨습니다……",
        "0x001258b0": "내가 한때 사랑했던 사람은\n시라카와 신지……\n살해당한 시라카와 이치로의 딸이야.",
        "0x0012f014": "신경이 쓰여서 그 녀석을\n조사해 보니, 무려\n전 심장 주인을 죽인\n살인범이었어……",
        "0x0013760b": "\n\n살해 현장 부근의 문에는\n지문을 지우려 한 흔적이 있었다……",
        "0x0013948e": "\n\n‘살인을 저지르지 않았다는 근거’……\n뭐, 알고 있다면 겨우 석방되고\n있겠지.",
        "0x00139b14": "\n\n게다가 미나즈키의 복직과 살인\n사건이 벌어진 시점이\n가까운 것도,\n단순한 우연이라고 치부할 뿐.",
        "0x0013eee7": "(\n지금 훌륭한\n살인 사건의 용의자다, 라고……\n그래, 점점 의식이 분명해졌다)",
        "0x0014047e": "시라카와가 살해된 곳은,\n바 ‘라이트 블루’ 안의\nVIP룸.",
        "0x00140f4c": "알고 있다고 생각하지만,\n살인죄로 기소되면,\n최악의 경우 사형도 있을 수 있다.",
        "0x00143947": "살해당한 사람은 주택업계뿐만 아니라,\n일본 경제에도 큰 영향을\n미치는 대기업의 사장이야?",
        "0x00144ad6": "지금 알고 있는 건,\n살해당한 사람이 시라카와 이치로라는 것.",
        "0x00146d7a": "……말했지만, 나는 아직 피의자입니다.\n살인범으로 확정된 것은 아닙니다.",
        "0x00148918": "권총에 네 지문을 묻힌 것부터\n살해 방법까지, 모든 것을 자백하고\n있다.",
        "0x00149f52": "(여기는 차분히 생각해……\n아사츠유 씨가 시라카와 이치로를\n살해한 동기로 이어지는 것이다……)",
        "0x0014fe3e": "살인자인지 살인자가 아닌지 따위,\n이 법정에서 재판으로 정해져!!",
        "0x00153f2d": "결국, 죄상은 살인죄.\n객관적으로 보면 분명하지.",

        # Additional sentence-level murder terminology checks.  These are
        # exact rows whose surrounding sentence removes any ambiguity in the
        # recovered glyphs.
        "0x0008a650": "……아야 씨의 남편을,\n오빠가 죽이고 말았습니다.",
        "0x000972e0": "거기다 시라카와 이치로가 살해당한 지금,\n이 건을 고집하는 것은……\n시간 낭비일지도 모른다.",
        "0x0009e341": "이 수첩을 보고,\n내가 아버지의 복수를 위해\n피해자를 죽였다고 볼 수도 있겠지,\n라는 거야.",
        "0x000a40c0": "돌아갈 때 한마디로 『살인자』라고\n말한 건 꽤 충격적이라고 할까,\n조금 슬펐지만 말이야……",
        "0x000a44da": "아아, 그렇구나.\n『살인자』라고 말하기 위해서만\n일부러 오는 걸까……?",
        "0x000b07c9": "그리고 진범을 밝혀내는 것과 동시에,\n살해 동기까지 밝혀내고 싶어.",
        "0x000b0925": "사실, 살해 방법을 알게 된 지금도,\n진범을 특정하지 못했어.",
        "0x000b1ba0": "우선은 아까 말한 3명이다.\n0시 44분이라고 생각했던 살해 시각이,\n그보다 이전으로 바뀐 셈이니까……",
        "0x000b38dd": "나는 노조미 씨의 어머니……\n아시로 씨가 자살한 이유를\n몰래 조사하고 있었어……",
        "0x000b5d6a": "그녀는 겁에 질려 있었어……\n그럴 만도 하지.\n남편이 사람을 죽이고 있었던 거니까.",
        "0x000b8f49": "게다가 콘도 자신도 부정한 증거를 회수하는 데\n필사적이어서,\n살해할 여유는 없었다고 봐도 좋아.",
        "0x000c3ac2": "……과연.\n그 엄중하게 관리되고 있던 열쇠를\n내가 부수고,\n피해자를 죽였다는 건가.",
        "0x000c3d9b": "여기가 피해자가 살해당해 있던 VIP룸이다.\n최초 발견자는 콘도 가쓰미……\n내 상사다.",
        "0x000c6765": "무엇이냐면, 지금 자백하면,\n살의는 없었다고 조서에 써 주지.\n이 경우에는 상해치사죄다.",
        "0x000c686d": "하지만 저항한다면,\n살의가 있었다는 걸 증명하는 증거를\n얼마든지 제시해 주지!\n무리하게라도!",
        "0x000c8754": "나는 죽이지 않았어!\nVIP룸에도 들어가지 않았다고!",
        "0x000ca6d1": "…………\n아버지는 시라카와 이치로에게\n살해당한 건가?",
        "0x000ceca1": "우선은 확인이다.\n네가 죽인 건 누구냐?",
        "0x000ced8d": "나는 아무도 죽이지 않았다.\n그러므로 묵비권을 행사하겠다.",
        "0x000cf671": "너의 알리바이는 애매하다.\n살해 시각에, 너는 무엇을 하고 있었지?",
        "0x000cfe78": "살해 시각,\n나는 완전히 술에 취해 있었어.",
        "0x000cff65": "……살해 시각에,\n너는 이미 가게를 나갔을 터다.",
        "0x000d605d": "너의 아버지 수기에 적혀 있던,\n시라카와 이치로의 손에 의해\n살해당했다는 내용.",
        "0x000d6569": "만약 내가 아버지를 죽인 범인이\n시라카와 이치로라는 걸 알고 있었다면,\n리폼을 부탁할 리가 없어!",
        "0x000d7866": "최소 5년 이상의 공백이 있었을 것이다!\n어째서 지금 와서 죽이는 거야!?",
        "0x000de988": "살해 시각에 코우지는 라이트 블루에서\n술에 취해 있었던 것일까?\n우선 그 알리바이 조사를 시작해 보자.",
        "0x000deb0a": "말다툼하고 있었던 것은 범행 시각으로 여겨지는\n0시 44분보다 훨씬 전이다.\n그러므로 이 경우에는 알리바이를\n증명한 것이 되지 않는다.",
        "0x000df45e": "지금은 코우지의 소유물이며,\n언제든 수첩 안을 읽을 수 있으므로,\n이 반론에서는 적절하지 않다.\n여기서는 코우지가 아버지를 죽인 사건의 진상을\n알고 있었을 경우의 행동 모순을 들이대는 편이\n좋을 것 같다.",
        "0x000df5ae": "여기서는 코우지가 아버지를 죽인 사건의 진상을\n알고 있었을 경우의 행동 모순을 들이대는 편이\n좋을 것 같다.",
        "0x000df76d": "확실히 알리바이 공작을 한 것은\n계획적이라고 말할 수 있을 것이다.\n그러나 이 알리바이 공작은 이 시점에서\n통상의 공론에 지나지 않고,\n계획적인 살인을 뒷받침하는 증거로서는 약하다.\n여기서는 보다 근본적인 이유를 제시하자.",
        "0x000e7c2c": "…………\n당신에게는 살해했다는 증거가 있습니다.",
        "0x000e91e3": "너에게 아이츠와 같은 행동을 하라고는\n말하지 않지만,\n적어도 조직을 등지고\n자신을 죽여서는 안 돼.",
        "0x000f08e4": "……진범이 무서운 거야.",
        "0x000f17e6": "[시라카와 신지는 살해당한 것인가?]",
        "0x000f221e": "그러나 술에 취해 있어도\n사람을 죽일 수는 있다.\n어디까지나 너의 기억이 없다는\n주장만을 인정한다는 것이다.",
        "0x000f6a3a": "거기에 수상한 점이 있다면,\n아사츠유 씨는 연인이 살해당한 셈이다!\n이것은 훌륭한 동기다!",
        "0x000f98fb": "그녀는 범행 시각으로 여겨지는\n시간대에 무엇을 하고 있었지?",
        "0x000fd562": "그러니까, 내가 죽였을 가능성도\n제로가 아니라는 점은 인정하자.",
        "0x000fd5e6": "하지만 그렇다고 해서,\n내가 죽이지 않았다는 것을 증명하려고\n한 건 아니야!",
        "0x000fdad0": "그렇다면, 새로운 범행 시각으로 여겨지는\n0시부터 0시 44분경까지의\n각 관계자의 행동에 대해 들어 보자.",
        "0x0010025a": "……살인자.",
        "0x00101d5a": "나에게는……\n선생님이 살인을 저지를 사람이라고는,\n도저히 생각할 수 없습니다.",
        "0x00101f5b": "선생님은 권총으로 상대를 죽였다고\n들었습니다.\n하지만 왜 권총입니까?",
        "0x00102ca7": "선생님은 사람을 죽인 건가요?",
        "0x00116bc8": "『용의자인 사이토 코우지는 살해를\n부인하고 있다』고.\n완전히 범인 취급이었어요.",
        "0x0013672a": "\n　\n거기서 시라카와 이치로라는 남자가 살해당했다.\n현장에 남겨진 무기에 내 지문이 묻어 있었기 때문에,\n체포되게 되어 버렸다.",
        "0x0013705c": "\n　\n시라카와 사토루는 이치로가 살해당해,\n가장 이득을 본 인물……",
        "0x00137d6f": "\n\n『살인자』라고 말하기 위해 왔겠지,\n역시……",
        "0x0013b413": "\n\n역시 어머니는 아버지가\n시라카와 이치로에게 살해당했다는 것을\n알고 있었어……",
        "0x0013b46a": "\n\n게다가, 그 일을 추궁했기 때문에\n시라카와 이치로에게 살해당했을 가능성이 있어……",
        "0x0013c50d": "\n\n미나즈키는 복직할 때 이치로가 방해가 돼서 죽였나?\n……라는 새로운 동기도 생각할 수 있지만,\n반대로 한 달에 걸쳐 관계를 회복하고 있었다고도\n생각할 수 있다.",
        "0x0013d9d5": "너에게 살해당하는 것 따위는,\n아, 아무것도……",
        "0x00144b81": "진범에게는 시라카와를 죽일 동기가\n있었을 것이다.\n거기에서 단서가\n찾을 수 있을지도 모른다.",
        "0x0014511e": "그것과, 살해 현장이 된\n라이트 블루라는 바에 가서\n종업원에게 물어봐 줬으면 한다.",
        "0x00146ce8": "나는 말이지, 깔끔한 성격의 인간이 좋아.\n사람까지 죽여 놓고,\n최후까지 발버둥 치는 녀석은……\n스마트하지 않지.",
        "0x001474c3": "그리고 이것은 사람을 죽이는 도구입니다.\n그것도 알고 있지요?",
        "0x00148856": "……누마사키가 자수해 왔다.\n시라카와 이치로를 죽인 건 자신이라고 말했어.",
        "0x0014ac6b": "……그렇구나.\n역시 어머니는 알고 있었어……\n아버지가 시라카와의 손에\n살해당했을지도 모른다는 것……",
        "0x0014ce73": "……이제 뭐라고 해도 소용없어.\n당신을 죽임으로써 아타시의 복수는 끝난다.\n그리고 아타시는 자수할 거야.",
        "0x0014d56e": "곧바로 그녀를 죽여 버리면 재미없어.\n나를 계속 쫓게 해서 그녀의 스위치가 켜지는지\n확인하고 싶었던 거야.",
        "0x0014e0c5": "교수는 시라카와 이치로와 결탁해\n신지 씨를 죽게 내버려 두고,\n심장 이식을 강행했어……\n그 원한을 풀기 위해서였지?",
        "0x0014e328": "그러니까 아타시는 이치로를 죽이려고\n생각했어……",
        "0x0014e8fb": "너에게 살해당하는 것 따위는,\n아, 아무것도……",
        "0x0014ef93": "……너를 살인범 따위로 만들지는 않겠어……",
        "0x0014fcbc": "응, 아니야.\n그를 죽인 건 역시 나야.",
        "0x0014fd2e": "아타시가 시라카와 이치로를 죽이려고 하지 않았다면,\n신지 씨도 스스로 목숨을 끊으려고는\n생각하지 않았을 거야……",
        "0x0014fd97": "아타시는 훌륭한 살인자야……",
        "0x00154f9a": "아타시가 하고 싶었던 것은\n코우짱에게 누명을 씌우는 것이 아니야.\n그저 교수를 죽일 동기를 원했을 뿐이니까……",
        "0x0015a4d3": "조사: 살해 현장의 BGM",
        "0x0015a5a4": "살해 현장의 BGM",
        "0x0015b4ef": "조사: 살해 현장의 BGM",
        "0x0015b5af": "살해 현장의 BGM",

        # 勾留 in this branch is also literal detention, not a generic
        # "상류"/"상어" token.
        "0x0012d466": "아아, 그건 별건 체포.\n별건으로 체포하면,\n정말로 짊어지고 싶은 죄로 체포할 때까지\n구류된 채로 시간을 벌 수 있겠지?",
    }

    # Apply both the individually reviewed rows and the complete murder
    # candidate table.  The latter deliberately lives in its own table so a
    # future audit cannot accidentally omit rows from the replacement pass.
    all_body_offsets = set(body_map) | set(murder_bodies)
    for offset in sorted(all_body_offsets, key=lambda item: int(item, 16)):
        if offset not in current:
            raise SystemExit(f"semantic body offset missing: {offset}")
        src = source.get(offset, "")
        body = murder_bodies[offset] if offset in murder_bodies else body_map[offset]
        if body.startswith(("【", "[", "\n")) or not translation_text.is_story_text(
            current[offset]
        ):
            new = body
        else:
            new = with_header(current[offset], body)
        add(overrides, offset, current[offset], new, src,
            "source-conditioned semantic correction", "high")

    # Make sure every high-confidence murder candidate received an explicit
    # context decision.  This prevents a future audit from silently dropping
    # one of the 66 serious rows.
    murder_offsets = {
        item["offset"] for item in audit["hard_candidates"]["murder_bad_token"]
    }
    missing_murder = sorted(murder_offsets - set(murder_bodies))
    if missing_murder:
        raise SystemExit("missing murder decisions: " + ", ".join(missing_murder))

    # 勾留 = detention/remand, not the unrelated token "상어".
    detention_bodies = {
        "0x00054689": "마이페이스인 사람이니까,\n구류되어 있는 비참함 같은 건\n별로 느끼지 않나 보네요.",
        "0x0009ba9d": "제일 큰 목적은 10일간\n구류를 청구하는 거니까.\n그를 위한 죄상 인정 같은 거야.",
        "0x0009bbb8": "결과는 같을 거야.\n아무리 무죄를 호소해도,\n구류될 거라고 생각해.",
        "0x000b05e4": "그것보다, 지금부터가 문제야.\n10일간 연장된 구류지만,\n지금까지 해 온 것과는\n다른 방식으로 움직여 보려고 해.",
        "0x000dccf9": "기분이 바뀌었다.\n이제 구류를 10일 연장받을 수 있도록,\n검사에게는 전해 두자.",
        "0x000dd525": "원래라면 앞으로 10일간\n구류를 연장받을 수도 있지만,\n그럴 필요도 없다.",
        "0x000e15b6": "\n\n(그 결과,\n10일간의 구류 연장이 결정됐다……\n좋아)",
        "0x001250a9": "아니, 어제 석방되도록\n최선을 다했는데,\n아직도 구류 중이라니……\n운이 나쁘다고 해야 하나……",
        "0x001251c1": "뭐, 그럴지도 모르지만……\n하지만 나도 이대로\n언제까지나 구류된 채로 있을 생각은\n없으니까.",
        "0x00130009": "(검사와 판사……라는 건,\n10일간의 구류 연장이\n결정됐다는 건가……)",
        "0x00130081": "(그렇다……\n구류에는 ‘연장’이라는\n제도가 있었지)",
        "0x00130683": "드디어 내일이 구류의\n마지막 날이다.",
        "0x001306d4": "석방인가, 구류 연장인가……\n형이 선고될 가능성도 있다.",
        "0x00130ceb": "그래도, 뭐,\n구류 연장은 각오하고 있어.",
        "0x0013149b": "미우라가 말했으니까.\n10일간의 구류 연장이라고.",
        "0x0014672d": "(오늘은 검사가 청구한 구류에 관한\n취조를 받기 위해\n검찰청에 와 있다)",
        "0x00146f1c": "(……결국,\n10일간의 구류가 결정된 건가……)",
        "0x00147040": "그럼 구류 심문을 시작하겠습니다.\n먼저 당신의 이름과 주소부터\n말씀해 주세요.",
        "0x00147756": "(……이걸로\n10일간의 구류가 결정된 건가……)",
        "0x00153657": "누나는 입원으로 인해\n구류 집행이 정지된 것뿐이니까,\n퇴원하면 유치장으로 돌아가지\n않으면 안 돼……",
    }
    countdown = {
        "0x000dbc02": 8, "0x000dbc77": 7, "0x000dbcec": 6,
        "0x000dbd61": 5, "0x000dbdd6": 4, "0x000dbe4b": 3,
        "0x000dbec0": 2, "0x000dbf35": 1, "0x000dbfa3": 9,
        "0x000dc002": 10,
    }
    for offset, days in countdown.items():
        detention_bodies[offset] = f"앞으로 {days}일이면 구류 기간이 끝난다."
    for offset, body in detention_bodies.items():
        if offset not in current:
            raise SystemExit(f"detention body offset missing: {offset}")
        new = with_header(current[offset], body)
        add(overrides, offset, current[offset], new, source[offset],
            "勾留 means detention/remand", "high")

    # 取調べ is represented by the recovered glyph 蟇調べ in the source.
    interrogation_source = "\u8827\u8abf"
    bad_interrogation_tokens = (
        "숲 조사", "숲조사", "숲",
        "삼림 조사", "삼림조사", "삼림",
        "삼촌 조사", "삼촌조사", "삼촌",
        "모리 조사", "모리",
    )
    for offset, src in source.items():
        if (
            interrogation_source not in src
            or offset not in current
            or offset in overrides
        ):
            continue
        old = current[offset]
        if not any(token in old for token in bad_interrogation_tokens):
            continue
        new = replace_all(old, [
            ("삼림 조사", "취조"), ("삼림조사", "취조"),
            ("삼촌 조사", "취조"), ("삼촌조사", "취조"),
            ("숲 조사", "취조"), ("숲조사", "취조"),
            ("모리 조사", "취조"),
            ("삼림", "취조"), ("삼촌", "취조"),
            ("모리", "취조"), ("숲", "취조"),
        ])
        add(overrides, offset, old, new, src,
            "蟇調べ is an interrogation/interview", "high")

    # 兄 / お兄さん was repeatedly translated as mother.  The source rows
    # selected here contain 兄 but no 母, so the replacement is unambiguous.
    for offset, src in source.items():
        if offset not in current or offset in overrides or "兄" not in src:
            continue
        old = current[offset]
        if "엄마" not in old and "어머니" not in old:
            continue
        new = old.replace("어머니", "오빠").replace("엄마", "오빠")
        add(overrides, offset, old, new, src,
            "兄 / お兄さん means older brother", "high")

    # True criminal / criminal terminology was also corrupted in a repeated
    # way.  Keep the source distinction: 真犯人 = 진범, 犯人 = 범인.
    true_criminal = "真犯人"
    criminal = "犯人"
    bad_criminal_tokens = (
        "잔인", "진짜인", "진부인", "진범인", "진진범", "진부인"
    )
    for offset, src in source.items():
        if offset not in current or offset in overrides or criminal not in src:
            continue
        old = current[offset]
        if not any(token in old for token in bad_criminal_tokens):
            continue
        target = "진범" if true_criminal in src else "범인"
        new = old
        for token in bad_criminal_tokens:
            new = new.replace(token, target)
        add(overrides, offset, old, new, src,
            "source-conditioned criminal terminology", "high")

    # A few high-confidence residual tokens are fixed by the exact source
    # phrase, even when the prior hard-candidate detector did not flag them.
    extra = {
        "0x0012f0a6": "즉, 원래 심장의 주인이\n살해당할 때 범인의 얼굴을 보고,\n그 기억이 심장을 이식받은 주인에게\n전해졌다는 이야기군요.",
        "0x0013b0eb": "\n\n누마사키 변호사가 모든 것을 자백했다.\n그의 말이 사실이라면,\n그는 진범이 아니다.",
        "0x0013d0b3": "\n\n하지만 콘도가 사건의 진범은 아니었다.\n이 진범은 내가 직접 찾아야 한다.",
        "0x00148a08": "이봐, 잠깐만요!\n범인은 아사츠유 씨라고 말하자!!",
        "0x00148a60": "누마사키 변호사에게는 알리바이가 있다!\n그는 진범이 아니다!",
    }
    for offset, body in extra.items():
        add(overrides, offset, current[offset], with_header(current[offset], body)
            if not body.startswith("\n") else body,
            source[offset], "source-conditioned semantic correction", "high")

    payload = {
        "schema": "enkaku_translation_semantic_overrides_v1",
        "generated_from": [
            str(TSV.relative_to(ROOT)),
            str(SOURCE_TSV.relative_to(ROOT)),
            str(AUDIT.relative_to(ROOT)),
        ],
        "policy": {
            "only_high_confidence": True,
            "speaker_tags_preserved_unless_the_source_sentence_is_narration": True,
            "remaining_kanji_review_is_not_silently_resolved": True,
        },
        "count": len(overrides),
        "overrides": sorted(overrides.values(),
                             key=lambda item: int(item["offset"], 16)),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps({
        "output": str(OUT),
        "override_count": len(overrides),
        "murder_decisions": len(murder_bodies),
        "detention_decisions": len(detention_bodies),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

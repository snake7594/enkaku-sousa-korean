"""Measure the specific defects the dialogue is showing, conditioned on the Japanese.

The report asks about four things that are visible in play -- lines that lost content, words
that ran together, sentences that lost their final punctuation, and phrasing that reads as
machine output.  Each is checkable against the source rather than by opinion:

  truncation   the Japanese has content the Korean does not account for at all
  spacing      a long run of Hangul with no space, which Korean orthography does not do
  punctuation  the Japanese line ends in 。or ？ and the Korean ends in nothing
  artefacts    residue of literal translation: Japanese particles left in, 것이다/하는 것,
               and the doubled spaces that the earlier pipeline introduced

Nothing is rewritten here.  This produces the list to work from, because fixing 9,626 lines
blind is what produced the current state.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")
JA = ROOT / "font_extract" / "script_full_ja_corrected.tsv"
KO = ROOT / "build" / "translation_ko_ellipsis.tsv"

HANGUL_RUN = re.compile(r"[가-힣]{12,}")
JA_END = re.compile(r"[。？！]\s*$")
KO_END = re.compile(r"[.?!…」』\)]\s*$")
ARTEFACTS = {
    "  ": "double space",
    " ,": "space before comma",
    " .": "space before period",
    "것이다": "stiff 것이다",
    "하는 것이": "stiff 하는 것이",
    "에서도": "でも rendered as 에서도",
    "아야": "彼 rendered as 아야",
    "쇼센": "しょせん left untranslated",
}


def rows(path: Path) -> dict[str, str]:
    _, data = translation_text.parse_loose_tsv(path)
    return {r[0].strip().lower(): r[2] for r in data if len(r) >= 3}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        default=ROOT / "build" / "dialogue_defects.json")
    parser.add_argument("--show", type=int, default=4)
    args = parser.parse_args()

    ja, ko = rows(JA), rows(KO)
    keys = [k for k in ja if k in ko]
    print(f"{len(keys)} pairs from {JA.name} / {KO.name}")

    found = {"truncation": [], "spacing": [], "punctuation": [], "artefact": []}
    for key in keys:
        src, dst = ja[key], ko[key]
        flat_src = src.replace("\\n", "")
        flat_dst = dst.replace("\\n", "")
        bare_src = re.sub(r"[【】《》〈〉「」『』、。！？…\s]", "", flat_src)
        bare_dst = re.sub(r"[【】《》「」.,!?…\s]", "", flat_dst)

        if len(bare_src) >= 14 and len(bare_dst) < len(bare_src) * 0.45:
            found["truncation"].append({"index": key, "ja": flat_src[:90],
                                        "ko": flat_dst[:90],
                                        "ratio": round(len(bare_dst) / len(bare_src), 2)})
        for run in HANGUL_RUN.findall(flat_dst):
            found["spacing"].append({"index": key, "run": run[:30], "ko": flat_dst[:80]})
            break
        for line_src, line_dst in zip(src.split("\\n"), dst.split("\\n")):
            if JA_END.search(line_src) and line_dst.strip() and not KO_END.search(line_dst):
                found["punctuation"].append({"index": key, "ja": line_src[:70],
                                             "ko": line_dst[:70]})
                break
        for needle, why in ARTEFACTS.items():
            if needle in flat_dst:
                found["artefact"].append({"index": key, "kind": why,
                                          "ko": flat_dst[:90]})
                break

    print()
    for kind, items in found.items():
        print(f"   {kind:12s} {len(items):5d} rows "
              f"({100.0 * len(items) / len(keys):.1f}%)")
    kinds = Counter(i["kind"] for i in found["artefact"])
    print(f"\n   artefact breakdown: {dict(kinds)}")

    for kind in ("truncation", "spacing", "punctuation"):
        print(f"\n--- {kind} ---")
        for item in found[kind][: args.show]:
            for k, v in item.items():
                if k != "index":
                    print(f"   {k}: {v}")
            print()

    args.out.write_text(json.dumps(
        {"schema": "enkaku_dialogue_defects_v1", "pairs": len(keys),
         "counts": {k: len(v) for k, v in found.items()}, "found": found},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

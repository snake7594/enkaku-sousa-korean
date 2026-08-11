"""Find rows whose Korean does not correspond to its Japanese, using names as the anchor.

Line structure caught the 200-row displacement because that stretch was shifted wholesale.
The block around 6230 is not shifted, it is scrambled -- 【三浦】's speech about the fingerprint
on the pistol sits where 【光志】 is talking about 朝露's dead fiance -- and no displacement
value describes it, so the structural test walked straight past.

Proper nouns do describe it.  A person named in the Japanese is named in the Korean, and the
transliteration is fixed across the whole script, so a row that says 朝露 and 白川一朗 while
its Korean says neither is a row that is not a translation of it.  Counting in both directions
keeps the test honest: the Korean naming someone the Japanese never mentions is the same
defect seen from the other side.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")

NAMES = {
    "朝露": "아사츠유", "三浦": "미우라", "近藤": "콘도", "法子": "노리코",
    "白川": "시라카와", "斉藤": "사이토", "吉本": "요시모토", "七芝": "나나시바",
    "中川": "나카가와", "樋口": "히구치", "栄太郎": "에이타로", "晋太郎": "신타로",
    "のぞみ": "노조미", "茜": "아카네", "葵": "아오이", "悟": "사토루",
    "真二": "신지", "沼崎": "누마사키", "水無月": "미나즈키", "一朗": "이치로",
    "志朗": "시로", "美佐恵": "미사에", "安代": "야스요", "克美": "가쓰미",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ja", type=Path,
                        default=ROOT / "font_extract" / "script_full_ja_v5.tsv")
    parser.add_argument("--ko", type=Path, default=ROOT / "build" / "translation_ko_v3.tsv")
    parser.add_argument("--window", type=int, default=50)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "correspondence.json")
    args = parser.parse_args()

    _, ja_rows = translation_text.parse_loose_tsv(args.ja)
    _, ko_rows = translation_text.parse_loose_tsv(args.ko)
    ja = [r for r in ja_rows if len(r) >= 3]
    ko = [r for r in ko_rows if len(r) >= 3]

    flags = []
    for i, (a, b) in enumerate(zip(ja, ko)):
        # a speaker label is not evidence about the body, so compare the body only
        src = a[2].split("】", 1)[-1]
        dst = b[2].split("】", 1)[-1]
        missing = [j for j, k in NAMES.items() if j in src and k not in dst]
        spurious = [k for j, k in NAMES.items() if k in dst and j not in src]
        # 悟 also means "realise"; 茜/葵 are short.  Require a name to be missing AND another
        # to be invented before calling a row wrong -- either alone is normal paraphrase.
        if missing and spurious:
            flags.append({"index": i, "offset": a[0], "missing": missing,
                          "spurious": spurious, "ja": src[:56], "ko": dst[:56]})

    dens = []
    for lo in range(0, len(ja), args.window):
        n = sum(1 for f in flags if lo <= f["index"] < lo + args.window)
        if n:
            dens.append((lo, min(lo + args.window, len(ja)), n))
    dens.sort(key=lambda d: -d[2])

    args.out.write_text(json.dumps(
        {"schema": "enkaku_correspondence_v1", "rows": len(ja), "flagged": len(flags),
         "worst_windows": [{"from_index": a, "to_index": b, "flagged": n}
                           for a, b, n in dens[:15]],
         "flags": flags}, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(flags)} of {len(ja)} rows name someone the other side does not "
          f"({100.0 * len(flags) / len(ja):.2f}%)\n")
    print(f"densest {args.window}-row windows:")
    for a, b, n in dens[:10]:
        print(f"   idx {a:5d}..{b:<5d} {n:3d} rows  ({100.0 * n / args.window:.0f}%)")
    print()
    for f in flags[:5]:
        print(f"   {f['offset']}  missing {f['missing']}  invented {f['spurious']}")
        print(f"      JA {f['ja']}")
        print(f"      KO {f['ko']}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

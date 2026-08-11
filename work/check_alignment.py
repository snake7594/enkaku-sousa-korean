"""Check that each Korean row really is the translation of the Japanese row it sits on.

Speaker tags alone cannot answer this.  These scenes alternate two speakers, so a row whose
label is simply wrong looks exactly like a row whose content belongs to its neighbour.

Line structure can answer it.  The translation keeps the engine's literal \\n breaks, so a
four-line Japanese row is a four-line Korean row, and that shape survives translation while
meaning it does not.  Scoring each row against its own Japanese and against its neighbours
shows whether a run of rows is genuinely displaced or merely mislabelled.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")
RUBY = re.compile(r"《[^》]*》")


def shape(text: str) -> tuple:
    body = RUBY.sub("", text)
    body = re.sub(r"^【[^】]*】", "", body)
    lines = body.split("\\n")
    return (len(lines), tuple(1 if l.strip() else 0 for l in lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ja", type=Path,
                        default=ROOT / "font_extract" / "script_full_ja_v5.tsv")
    parser.add_argument("--ko", type=Path,
                        default=ROOT / "build" / "translation_ko_v2_kayo.tsv")
    parser.add_argument("--window", type=int, default=8)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "alignment.json")
    args = parser.parse_args()

    _, ja_rows = translation_text.parse_loose_tsv(args.ja)
    _, ko_rows = translation_text.parse_loose_tsv(args.ko)
    ja = [r for r in ja_rows if len(r) >= 3]
    ko = [r for r in ko_rows if len(r) >= 3]

    js = [shape(r[2]) for r in ja]
    ks = [shape(r[2]) for r in ko]

    totals = {}
    for d in range(-args.window, args.window + 1):
        hit = sum(1 for i in range(len(ja))
                  if 0 <= i + d < len(ja) and js[i + d] == ks[i])
        totals[d] = hit

    # per row, which displacement fits -- only counted when it is unique
    best = []
    for i in range(len(ja)):
        fits = [d for d in range(-args.window, args.window + 1)
                if 0 <= i + d < len(ja) and js[i + d] == ks[i]]
        best.append(fits[0] if len(fits) == 1 else (0 if 0 in fits else None))

    runs, start = [], None
    for i, d in enumerate(best):
        bad = d not in (0, None)
        if bad and start is None:
            start = i
        elif not bad and start is not None:
            if i - start >= 3:
                runs.append((start, i - 1, best[start]))
            start = None

    report = [{"from": ja[lo][0], "to": ja[hi][0], "rows": hi - lo + 1, "displacement": d,
               "ja": ja[lo][2][:60], "ko": ko[lo][2][:60]} for lo, hi, d in runs]
    args.out.write_text(json.dumps(
        {"schema": "enkaku_alignment_v1", "rows": len(ja),
         "shape_matches_by_displacement": {str(k): v for k, v in sorted(totals.items())},
         "runs": len(runs), "detail": report}, ensure_ascii=False, indent=1), encoding="utf-8")

    print("rows whose line shape matches, by displacement:")
    for d in sorted(totals):
        bar = "#" * round(totals[d] / max(totals.values()) * 46)
        print(f"  {d:+3d}  {totals[d]:6d}  {bar}")
    print(f"\n{len(runs)} runs of 3+ rows fit a displacement other than 0")
    for r in report[:12]:
        print(f"   {r['from']} .. {r['to']}  {r['rows']:4d} rows, displaced {r['displacement']:+d}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

"""Find every stretch where the Korean rows sit against the wrong Japanese rows.

One such stretch is already known: from index 5600 the Korean at each row is the translation
of the row below it, so 【近藤】「覚悟しておくんだな！」 has no Korean at all and every line for
the next two hundred rows appears one row early.  In game that means the wrong speaker and
the wrong line, which is worse than any wording problem, so the rest of the script has to be
checked for the same thing rather than assumed clean.

Line structure is the evidence.  The translation keeps the engine's literal \\n breaks, so the
shape of a row -- how many lines, which are blank -- survives translation while the words do
not.  For each row this scores the shape of the Korean against a window of Japanese rows and
keeps the displacement that wins by a clear margin, then reports the runs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import translation_text
from check_alignment import shape

ROOT = Path(r"D:\psp\원격수사")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ja", type=Path,
                        default=ROOT / "font_extract" / "script_full_ja_v5.tsv")
    parser.add_argument("--ko", type=Path,
                        default=ROOT / "build" / "translation_ko_v2_kayo.tsv")
    parser.add_argument("--radius", type=int, default=10, help="rows either side to score over")
    parser.add_argument("--span", type=int, default=6, help="displacements to consider")
    parser.add_argument("--margin", type=int, default=3, help="votes a winner must lead by")
    parser.add_argument("--min-run", type=int, default=4)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "displaced_runs.json")
    args = parser.parse_args()

    _, ja_rows = translation_text.parse_loose_tsv(args.ja)
    _, ko_rows = translation_text.parse_loose_tsv(args.ko)
    ja = [r for r in ja_rows if len(r) >= 3]
    ko = [r for r in ko_rows if len(r) >= 3]
    js, ks = [shape(r[2]) for r in ja], [shape(r[2]) for r in ko]
    n = len(ja)

    verdict = []
    for i in range(n):
        lo, hi = max(0, i - args.radius), min(n, i + args.radius + 1)
        score = {}
        for d in range(-args.span, args.span + 1):
            score[d] = sum(1 for j in range(lo, hi) if 0 <= j + d < n and js[j + d] == ks[j])
        best = max(score, key=lambda d: (score[d], -abs(d)))
        verdict.append(best if best != 0 and score[best] >= score[0] + args.margin else 0)

    runs, start = [], None
    for i in range(n + 1):
        d = verdict[i] if i < n else 0
        if d and start is None:
            start = i
        elif (not d or (start is not None and verdict[start] != d)) and start is not None:
            if i - start >= args.min_run:
                runs.append((start, i - 1, verdict[start]))
            start = i if d else None

    detail = [{"first_index": lo, "last_index": hi, "from": ja[lo][0], "to": ja[hi][0],
               "rows": hi - lo + 1, "displacement": d,
               "ja_at_start": ja[lo][2][:60], "ko_at_start": ko[lo][2][:60]}
              for lo, hi, d in runs]
    args.out.write_text(json.dumps(
        {"schema": "enkaku_displaced_runs_v1", "rows": n, "runs": len(runs),
         "rows_displaced": sum(r["rows"] for r in detail), "detail": detail},
        ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(runs)} displaced runs of {args.min_run}+ rows, "
          f"{sum(r['rows'] for r in detail)} rows in total\n")
    for r in detail:
        print(f"   idx {r['first_index']:5d}..{r['last_index']:<5d} {r['from']} .. {r['to']}  "
              f"{r['rows']:4d} rows, displaced {r['displacement']:+d}")
        print(f"      JA {r['ja_at_start']}")
        print(f"      KO {r['ko_at_start']}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

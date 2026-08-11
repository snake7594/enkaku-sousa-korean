"""Find which rows the v2 retranslation never touched.

The block around index 6230 is scrambled -- 【三浦】's fingerprint speech sits under 【光志】's
lines about 朝露's dead fiance, and 시라카와 이치리 appears where the Japanese says nothing at
all.  No retranslation batch covers those indices, which is the explanation: they are left
over from the earlier pass and were never rewritten.

So this asks the question directly.  Every apply_retranslation_v2_*.py carries an explicit
index -> text table, and the union of those tables is what got the careful treatment.  What is
outside it is what still needs looking at, and knowing its size is the difference between
finishing the job and guessing that it is finished.
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")
WORK = ROOT / "work"


def batch_keys() -> dict[str, set[int]]:
    out = {}
    for path in sorted(WORK.glob("apply_retranslation_v2_*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        manual: dict[int, str] = {}
        for node in ast.walk(tree):
            value = None
            if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "MANUAL":
                value = node.value
            elif isinstance(node, ast.Assign) and any(
                    getattr(t, "id", "") == "MANUAL" for t in node.targets):
                value = node.value
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and node.func.attr == "update"
                  and getattr(node.func.value, "id", "") == "MANUAL" and node.args):
                value = node.args[0]
            if value is not None:
                try:
                    manual.update(ast.literal_eval(value))
                except (ValueError, TypeError):
                    pass
        if manual:
            out[path.name] = set(manual)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ja", type=Path,
                        default=ROOT / "font_extract" / "script_full_ja_v5.tsv")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "coverage.json")
    args = parser.parse_args()

    _, ja_rows = translation_text.parse_loose_tsv(args.ja)
    ja = [r for r in ja_rows if len(r) >= 3]
    batches = batch_keys()
    covered = set().union(*batches.values()) if batches else set()
    missing = sorted(set(range(len(ja))) - covered)

    runs, start = [], None
    for i in range(len(ja) + 1):
        gap = i in set(missing)
        if gap and start is None:
            start = i
        elif not gap and start is not None:
            runs.append((start, i - 1))
            start = None
    runs = [r for r in runs if r[1] - r[0] >= 4]

    detail = [{"first_index": lo, "last_index": hi, "rows": hi - lo + 1,
               "from": ja[lo][0], "to": ja[hi][0], "ja": ja[lo][2][:56]} for lo, hi in runs]
    args.out.write_text(json.dumps(
        {"schema": "enkaku_coverage_v1", "rows": len(ja), "batches": len(batches),
         "rows_retranslated": len(covered), "rows_untouched": len(missing),
         "runs_of_5_or_more": detail}, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(batches)} batches cover {len(covered)} of {len(ja)} rows "
          f"({100.0 * len(covered) / len(ja):.1f}%)")
    print(f"{len(missing)} rows were never retranslated, "
          f"in {len(runs)} runs of 5 or more\n")
    for r in sorted(detail, key=lambda d: -d["rows"])[:12]:
        print(f"   idx {r['first_index']:5d}..{r['last_index']:<5d} {r['from']} .. {r['to']}"
              f"  {r['rows']:4d} rows")
        print(f"      {r['ja']}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

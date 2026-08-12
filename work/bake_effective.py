"""Write out the text the build actually splices in, overrides and all.

`build_runtime_refs.py` does not use the TSV as given: unless told the translation is final it
reapplies the residual and semantic override ledgers on top, which rewrites 479 rows.  Those
rewrites are what the released game shows, so anything that measures or reshapes the shipped
text -- line widths, for one -- has to run on this, not on the TSV.

Baking them in and then building with --translation-is-final produces the same stream as
building from the TSV with the overrides live, which is the check at the bottom of this file's
usage: the two streams come out byte-identical.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tsv", type=Path, default=ROOT / "build" / "translation_ko_v6.tsv")
    parser.add_argument("--out", type=Path,
                        default=ROOT / "build" / "translation_ko_effective.tsv")
    args = parser.parse_args()

    header, rows = translation_text.parse_loose_tsv(args.tsv)
    effective = dict(translation_text.load_for_patch(args.tsv, apply_overrides=True))

    out, changed = [], 0
    for row in rows:
        row = list(row)
        if len(row) >= 3:
            text = effective.get(int(row[0], 16))
            if text is not None and text != row[2]:
                row[2] = text
                changed += 1
        out.append(row)

    args.out.write_text(header + "\n" + "\n".join("\t".join(r) for r in out) + "\n",
                        encoding="utf-8")
    print(f"{changed} rows carried an override\n-> {args.out}")


if __name__ == "__main__":
    main()

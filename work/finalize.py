"""Write the final deliverables: a tidy charmap (JSON + TSV) and the readable script."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

OUT = Path(r"D:\psp\원격수사\font_extract")
RAW = OUT / "script_full_raw.tsv"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--charmap", type=Path, required=True)
    parser.add_argument("--prefix", default="charmap_final",
                        help="basename for the .json/.tsv written into font_extract")
    args = parser.parse_args()

    table = json.loads(args.charmap.read_text(encoding="utf-8"))
    uses = Counter(int(m) for m in re.findall(r"\[(\d+)\]", RAW.read_text(encoding="utf-8")))

    final = []
    for entry in table:
        glyph = entry["index"]
        final.append({
            "index": glyph,
            "char": entry["char"],
            "source": entry["source"],
            "confidence": entry["confidence"],
            "uses": uses.get(glyph, 0),
            "alts": entry.get("alts", [])[:5],
        })
    (OUT / f"{args.prefix}.json").write_text(
        json.dumps(final, ensure_ascii=False, indent=1), encoding="utf-8")

    with (OUT / f"{args.prefix}.tsv").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("index\tchar\tsource\tconfidence\tuses\talts\n")
        for e in final:
            fh.write(f"{e['index']}\t{e['char']}\t{e['source']}\t{e['confidence']}\t"
                     f"{e['uses']}\t{''.join(e['alts'])}\n")

    print(f"{args.prefix}.json / .tsv written ({len(final)} glyphs)")
    tiers = Counter((e["source"], e["confidence"]) for e in final)
    total_uses = sum(uses.values())
    print(f"\n{'source':10s} {'conf':8s} {'glyphs':>7s} {'uses':>8s} {'share':>7s}")
    rows = sorted(tiers, key=lambda k: -sum(e["uses"] for e in final
                                            if (e["source"], e["confidence"]) == k))
    for key in rows:
        n_uses = sum(e["uses"] for e in final if (e["source"], e["confidence"]) == key)
        print(f"{key[0]:10s} {key[1]:8s} {tiers[key]:7d} {n_uses:8d} "
              f"{n_uses * 100 / total_uses:6.1f}%")
    trusted = sum(e["uses"] for e in final if e["source"] != "bitmap")
    print(f"\nevidence-backed occurrences: {trusted}/{total_uses} "
          f"({trusted * 100 / total_uses:.1f}%)")


if __name__ == "__main__":
    main()

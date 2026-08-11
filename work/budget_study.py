"""Quantify the byte-budget shortfall and test whether one-byte codes would close it.

Only 6% of translated lines fit when every syllable costs two bytes.  The format also
offers 146 one-byte codes (hiragana 0x28-0x7A and half-width katakana 0xA1-0xDF), whose
glyphs live in BOOT.BIN.  This simulates giving the most frequent syllables those codes
to see how far it gets, so the decision to invest in that path — or in relocating text
and rewriting pointers — is made on numbers rather than intuition.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import lzss
from encode_korean import PASSTHROUGH, run_end

SRC = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR\0000")
STREAM1 = 0x27E000
ONE_BYTE_SLOTS = 83 + 63     # hiragana range + half-width katakana range


def load(translation: Path) -> list[tuple[int, str]]:
    rows = []
    for line in translation.read_text(encoding="utf-8").splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) >= 3 and parts[2].strip():
            rows.append((int(parts[0], 16), parts[2].replace("\\n", "\n")))
    return rows


def cost(text: str, cheap: set[str]) -> int:
    total = 0
    for ch in text:
        if ch == "\n":
            total += 1
        elif ch in PASSTHROUGH:
            total += 2
        elif ch in cheap:
            total += 1
        else:
            total += 2
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translation", type=Path, required=True)
    args = parser.parse_args()

    rows = load(args.translation)
    plain = lzss.decompress(SRC.read_bytes(), STREAM1)[0]
    budgets = {offset: run_end(plain, offset) - offset for offset, _ in rows}

    counts = Counter()
    for _, text in rows:
        for ch in text:
            if ch != "\n" and ch not in PASSTHROUGH:
                counts[ch] += 1

    print(f"{len(rows)} translated lines, {sum(counts.values())} payload characters, "
          f"{len(counts)} distinct")
    total_budget = sum(budgets.values())

    print(f"\n{'cheap syllables':>16}  {'lines fitting':>13}  {'total bytes':>12}  {'vs budget':>10}")
    for n in (0, 64, 128, ONE_BYTE_SLOTS, 256, 512):
        cheap = {ch for ch, _ in counts.most_common(n)}
        fits = sum(1 for offset, text in rows if cost(text, cheap) <= budgets[offset])
        total = sum(cost(text, cheap) for _, text in rows)
        print(f"{n:>16}  {fits:>6} ({fits * 100 / len(rows):4.1f}%)  {total:>12}  "
              f"{total * 100 / total_budget:9.1f}%")

    cheap = {ch for ch, _ in counts.most_common(ONE_BYTE_SLOTS)}
    covered = sum(counts[ch] for ch in cheap) / max(1, sum(counts.values()))
    print(f"\ntop {ONE_BYTE_SLOTS} syllables cover {covered * 100:.1f}% of all characters")

    over = [(cost(text, cheap) - budgets[offset], offset) for offset, text in rows
            if cost(text, cheap) > budgets[offset]]
    if over:
        over.sort(reverse=True)
        excess = sum(o for o, _ in over)
        print(f"with one-byte codes: {len(over)} lines still over, {excess} bytes short in total")
        print(f"   worst line is {over[0][0]} bytes over (0x{over[0][1]:x})")
        print(f"   median shortfall {sorted(o for o, _ in over)[len(over) // 2]} bytes")


if __name__ == "__main__":
    main()

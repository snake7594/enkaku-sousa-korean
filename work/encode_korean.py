"""Write translated lines back into the script, inside each line's byte budget.

The bytecode addresses text by absolute offset, so a line may not change length.  Every
line therefore has a fixed budget: the bytes its original text occupied.  Korean costs
two bytes per syllable here, while the Japanese it replaces mixed one-byte kana with
two-byte kanji, so some lines will not fit — those are reported rather than silently
truncated, because a clipped line is worse than an untranslated one.

Line breaks are preserved as 0x11 and any leftover space is padded with the ideographic
space, which the engine draws as blank.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import lzss
from decode_script import HIRA, HIRA_BASE, LEAD_HI, LEAD_LO, kanji_code

SRC = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\USRDIR\0000")
STREAM1 = 0x27E000
IDEOGRAPHIC_SPACE = bytes([0x81, 0x40])
NEWLINE = 0x11

# characters the engine already has in its Shift-JIS block
PASSTHROUGH = {
    "　": bytes([0x81, 0x40]), "、": bytes([0x81, 0x41]), "。": bytes([0x81, 0x42]),
    "？": bytes([0x81, 0x48]), "！": bytes([0x81, 0x49]), "（": bytes([0x81, 0x69]),
    "）": bytes([0x81, 0x6A]), "【": bytes([0x81, 0x79]), "】": bytes([0x81, 0x7A]),
    "…": bytes([0x81, 0x63]), "・": bytes([0x81, 0x45]),
    "「": bytes([0x81, 0x75]), "」": bytes([0x81, 0x76]),
    " ": bytes([0x81, 0x40]),   # plain spaces become the ideographic space
}


def run_end(plain: bytes, start: int) -> int:
    """End of the text run at `start`, using the same tokenisation as extraction."""
    end = start
    n = len(plain)
    while end < n:
        b = plain[end]
        if b == 0x0F:
            end += 2 if (end + 1 < n and 0x31 <= plain[end + 1] <= 0x39) else 1
        elif b == NEWLINE:
            end += 1
        elif b == 0x16:
            end += 2
        elif LEAD_LO <= b <= LEAD_HI:
            end += 2
        elif HIRA_BASE <= b < HIRA_BASE + len(HIRA) or 0xA1 <= b <= 0xDF:
            end += 1
        else:
            break
    return end


def encode_text(text: str, slots: dict[str, int]) -> bytes | None:
    out = bytearray()
    for ch in text:
        if ch == "\n":
            out.append(NEWLINE)
        elif ch in PASSTHROUGH:
            out += PASSTHROUGH[ch]
        elif ch in slots:
            out += kanji_code(slots[ch])
        else:
            return None
    return bytes(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translation", type=Path, required=True)
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--stream", type=Path, required=True, help="stream with the Korean font")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    slots = {ch: int(i) for ch, i in json.loads(args.map.read_text(encoding="utf-8"))["slots"].items()}
    plain = bytearray(args.stream.read_bytes())
    original = lzss.decompress(SRC.read_bytes(), STREAM1)[0]
    if len(plain) != len(original):
        raise SystemExit("stream size mismatch")

    written = skipped = overflow = unknown = 0
    problems = []
    for line in args.translation.read_text(encoding="utf-8").splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        offset = int(parts[0], 16)
        text = parts[2].replace("\\n", "\n").strip()
        if not text:
            skipped += 1
            continue

        end = run_end(bytes(original), offset)
        budget = end - offset
        encoded = encode_text(text, slots)
        if encoded is None:
            unknown += 1
            problems.append((offset, "unmapped character", len(text), budget))
            continue
        if len(encoded) > budget:
            overflow += 1
            problems.append((offset, "too long", len(encoded), budget))
            continue

        pad = IDEOGRAPHIC_SPACE * ((budget - len(encoded)) // 2)
        tail = bytes([NEWLINE]) * (budget - len(encoded) - len(pad))
        plain[offset:end] = encoded + pad + tail
        written += 1

    args.out.write_bytes(bytes(plain))
    print(f"{written} lines written, {skipped} blank, {overflow} over budget, {unknown} unmapped")
    print(f"-> {args.out} ({len(plain)} bytes, size unchanged)")

    if problems:
        print(f"\nfirst problems:")
        for offset, why, got, budget in problems[:10]:
            print(f"   0x{offset:08x}  {why}: {got} vs budget {budget}")
    if args.report:
        args.report.write_text("\n".join(
            f"0x{o:08x}\t{w}\t{g}\t{b}" for o, w, g, b in problems), encoding="utf-8")
        print(f"-> {args.report}")


if __name__ == "__main__":
    main()

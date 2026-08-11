"""Extract every dialogue line from the script, without relying on opcode markers.

Keying off 07 1C missed about 9% of the text, because the engine opens text with
several different markers (07 81, 17, and others).  Instead this walks the whole
bytecode region and keeps every maximal run of text tokens, which is marker-agnostic.

Bytecode operands can look like hiragana, so a run only counts when it is long
enough and contains at least one two-byte token (kanji or punctuation) — bytecode
never produces those in sequence.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from decode_script import (HALFWIDTH, HIRA, HIRA_BASE, KANJI_HI, KANJI_LO,
                           LEAD_HI, LEAD_LO, STREAM, kanji_index)

TEXT_START = 0x2AC80
NEWLINE = 0x11
RUBY = 0x0F
MARKUP = 0x16


def decode_run(data: bytes, start: int, end: int) -> tuple[str, int, int]:
    """Return (text, count of text tokens, count of two-byte tokens)."""
    out = []
    tokens = wide = 0
    i = start
    in_ruby = False
    while i < end:
        b = data[i]
        if b == RUBY:
            if not in_ruby and i + 1 < end and 0x31 <= data[i + 1] <= 0x39:
                out.append("《")
                in_ruby = True
                i += 2
                continue
            out.append("》")
            in_ruby = False
            i += 1
            continue
        if b == NEWLINE:
            out.append("\n")
            i += 1
            continue
        if b == MARKUP:
            i += 2
            continue
        if LEAD_LO <= b <= LEAD_HI and i + 1 < end:
            trail = data[i + 1]
            if KANJI_LO <= b <= KANJI_HI:
                out.append(f"[{kanji_index(b, trail)}]")
            else:
                try:
                    out.append(bytes([b, trail]).decode("cp932"))
                except Exception:  # noqa: BLE001
                    out.append(f"<{b:02x}{trail:02x}>")
            tokens += 1
            wide += 1
            i += 2
            continue
        if HIRA_BASE <= b < HIRA_BASE + len(HIRA):
            out.append(HIRA[b - HIRA_BASE])
        elif 0xA1 <= b <= 0xDF:
            out.append(HALFWIDTH[b - 0xA1])
        else:
            break
        tokens += 1
        i += 1
    return "".join(out), tokens, wide


def find_runs(data: bytes, start: int, min_tokens: int, min_wide: int):
    runs = []
    i = start
    n = len(data)
    while i < n:
        b = data[i]
        is_text = (LEAD_LO <= b <= LEAD_HI) or (HIRA_BASE <= b < HIRA_BASE + len(HIRA)) \
            or (0xA1 <= b <= 0xDF)
        if not is_text:
            i += 1
            continue
        # walk forward to the end of the run
        j = i
        in_ruby = False
        while j < n:
            c = data[j]
            if c == RUBY:
                j += 2 if (not in_ruby and j + 1 < n and 0x31 <= data[j + 1] <= 0x39) else 1
                in_ruby = not in_ruby
                continue
            if c in (NEWLINE,):
                j += 1
                continue
            if c == MARKUP:
                j += 2
                continue
            if LEAD_LO <= c <= LEAD_HI and j + 1 < n:
                j += 2
                continue
            if HIRA_BASE <= c < HIRA_BASE + len(HIRA) or 0xA1 <= c <= 0xDF:
                j += 1
                continue
            break
        text, tokens, wide = decode_run(data, i, j)
        if tokens >= min_tokens and wide >= min_wide:
            runs.append((i, text))
        i = max(j, i + 1)
    return runs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-tokens", type=int, default=3)
    parser.add_argument("--min-wide", type=int, default=1)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--charmap", type=Path, default=None)
    parser.add_argument("--lines", type=int, default=10)
    args = parser.parse_args()

    data = STREAM.read_bytes()
    runs = find_runs(data, TEXT_START, args.min_tokens, args.min_wide)
    total_chars = sum(len(re.sub(r"\[\d+\]", "x", t)) for _, t in runs)
    kanji_refs = sum(len(re.findall(r"\[(\d+)\]", t)) for _, t in runs)
    print(f"{len(runs)} text runs, {total_chars} characters, {kanji_refs} kanji references")

    mapping = None
    if args.charmap:
        table = json.loads(args.charmap.read_text(encoding="utf-8"))
        mapping = {e["index"]: e["char"] for e in table}

    def render(text: str) -> str:
        if mapping is None:
            return text
        return re.sub(r"\[(\d+)\]", lambda m: mapping.get(int(m.group(1)), "□"), text)

    print("\nsample:")
    for offset, text in runs[: args.lines]:
        print(f"   0x{offset:08x}  " + render(text).replace("\n", " / "))

    if args.out:
        with args.out.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write("offset\tlines\ttext\n")
            for offset, text in runs:
                # in-game line breaks are kept as a literal \n so one run stays one row
                flat = render(text).replace("\n", "\\n")
                fh.write(f"0x{offset:08x}\t{text.count(chr(10)) + 1}\t{flat}\n")
        print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

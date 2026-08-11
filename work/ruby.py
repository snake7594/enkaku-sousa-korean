"""Ruby (furigana) parsing for the 원격수사 script.

Grammar (confirmed against 「[69][70] 0F '2' かんろく 0F があるわ」 = 「貫禄があるわ」):

    <base characters> 0F <ASCII digit n> <reading kana...> 0F <rest>

The digit gives how many preceding characters the reading annotates, so the base
is unambiguous even when kanji and kana are adjacent.
"""

from __future__ import annotations

from collections import Counter

from decode_script import kanji_index
from decode_script import (HALFWIDTH, HIRA, HIRA_BASE, KANJI_HI, KANJI_LO,
                           LEAD_HI, LEAD_LO, STREAM, kanji_index, text_spans)

RUBY = 0x0F
TAG_WITH_OPERAND = 0x16


def kana_of(b: int) -> str | None:
    if HIRA_BASE <= b < HIRA_BASE + len(HIRA):
        return HIRA[b - HIRA_BASE]
    if 0xA1 <= b <= 0xDF:
        return HALFWIDTH[b - 0xA1]
    return None


def tokenize(span: bytes) -> list[tuple[str, object]]:
    tokens: list[tuple[str, object]] = []
    i = 0
    n = len(span)
    while i < n:
        b = span[i]
        if b == RUBY:
            if i + 1 < n and 0x31 <= span[i + 1] <= 0x39:
                tokens.append(("ruby_open", span[i + 1] - 0x30))
                i += 2
            else:
                tokens.append(("ruby_close", None))
                i += 1
        elif b < 0x20:
            tokens.append(("ctrl", b))
            i += 2 if b == TAG_WITH_OPERAND else 1
        elif LEAD_LO <= b <= LEAD_HI and i + 1 < n:
            if KANJI_LO <= b <= KANJI_HI:
                tokens.append(("kanji", kanji_index(b, span[i + 1])))
            else:
                tokens.append(("punct", bytes([b, span[i + 1]])))
            i += 2
        else:
            kana = kana_of(b)
            tokens.append(("kana", kana) if kana else ("other", b))
            i += 1
    return tokens


def pairs_in(span: bytes) -> list[tuple[tuple[int, ...], str]]:
    tokens = tokenize(span)
    found = []
    for j, (kind, value) in enumerate(tokens):
        if kind != "ruby_open":
            continue
        count = int(value)
        reading = []
        k = j + 1
        while k < len(tokens) and tokens[k][0] == "kana":
            reading.append(tokens[k][1])
            k += 1
        if not reading or k >= len(tokens) or tokens[k][0] != "ruby_close":
            continue
        base = []
        m = j - 1
        while m >= 0 and len(base) < count and tokens[m][0] == "kanji":
            base.append(int(tokens[m][1]))
            m -= 1
        if len(base) != count:
            continue
        base.reverse()
        found.append((tuple(base), "".join(reading)))
    return found


def all_pairs() -> Counter:
    counts = Counter()
    for _, span in text_spans(STREAM.read_bytes()):
        for base, reading in pairs_in(span):
            counts[(base, reading)] += 1
    return counts

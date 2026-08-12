"""Search for the title menu in the game's own text encoding, not in Shift-JIS.

Every earlier hunt for 最初から and 続きから looked for them as Shift-JIS, UTF-8 or UTF-16 and
found nothing anywhere -- executables, archives, script.  That result is weaker than it looks,
because the game does not store its text in any of those.  Dialogue is written in a private
encoding: hiragana as one byte from 0x28, kanji as two bytes whose lead runs 0x88 to 0x8D and
whose index into the font is (lead - 0x88) * 253 + trail.  A menu drawn with the same font
would be stored the same way, and no amount of grepping for Shift-JIS would ever show it.

So this encodes the words the way the game does, using the charmap the font audit produced,
and looks for that.  It also tries the kana-only prefixes, since 「から」 and 「データ」 need no
kanji at all and would survive even if the kanji slots were assigned differently.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
FONT = ROOT / "font_extract"
ISO = ROOT / "iso_extract"

HIRA_BASE = 0x28
HIRA = ("あいうえおかがきぎくぐけげこごさざしじすずせぜそぞただちぢっつづてでとどなにぬねの"
        "はばぱひびぴふぶぷへべぺほぼぽまみむめもゃやゅゆょよらりるれろゎわゐゑをん")

WORDS = ["最初から", "続きから", "データインストール", "設定", "はじめから", "つづきから",
         "から", "きから", "データ", "インストール", "つづき", "はじめ"]


def kanji_code(index: int) -> bytes:
    return bytes([0x88 + index // 253, index % 253])


def build_encoder():
    charmap = json.loads((FONT / "charmap_v5.json").read_text(encoding="utf-8"))["map"]
    slots = {}
    for key, char in charmap.items():
        slots.setdefault(char, int(key))
    hira = {ch: bytes([HIRA_BASE + n]) for n, ch in enumerate(HIRA)}
    # half-width katakana occupy 0xA1..0xDF in the same order the JIS row does
    kata_full = "。「」、・ヲァィゥェォャュョッーアイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワン゛゜"
    kata = {ch: bytes([0xA1 + n]) for n, ch in enumerate(kata_full)}

    def encode(text: str):
        out = bytearray()
        for ch in text:
            if ch in hira:
                out += hira[ch]
            elif ch in kata:
                out += kata[ch]
            elif ch in slots:
                out += kanji_code(slots[ch])
            else:
                return None
        return bytes(out)

    return encode, slots


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "title_encoded.json")
    args = parser.parse_args()

    encode, slots = build_encoder()
    needles = {}
    for word in WORDS:
        code = encode(word)
        needles[word] = code
        missing = [c for c in word if c not in slots and encode(c) is None]
        print(f"   {word:12s} -> {code.hex(' ') if code else 'NOT ENCODABLE ' + ''.join(missing)}")

    files = sorted(p for p in ISO.rglob("*") if p.is_file() and p.stat().st_size > 1024)
    files += [ROOT / "build" / "stream0.bin", ROOT / "build" / "stream1_ko_font_clean.bin"]
    hits = []
    print()
    for path in files:
        blob = path.read_bytes()
        for word, code in needles.items():
            if not code or len(code) < 4:
                continue
            at = blob.find(code)
            while at >= 0:
                hits.append({"file": path.name, "word": word, "offset": at,
                             "context": blob[max(0, at - 8):at + len(code) + 8].hex(" ")})
                at = blob.find(code, at + 1)
                if len(hits) > 400:
                    break

    args.out.write_text(json.dumps({"schema": "enkaku_title_encoded_v1",
                                    "needles": {k: (v.hex(" ") if v else None)
                                                for k, v in needles.items()},
                                    "hits": hits}, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"{len(hits)} hits across {len(files)} files")
    for h in hits[:25]:
        print(f"   {h['file']:14s} {h['word']:12s} at {h['offset']:#010x}   {h['context']}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

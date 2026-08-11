"""Look for the title-menu wording as text in the executables.

No texture stream in any USRDIR file holds these labels -- 0001-0023 and the 404 MB 0012
were all scanned.  That leaves the possibility that the game draws them as text rather than
blitting an image, in which case the wording lives in an executable as Shift-JIS.

Searched in both BOOT.BIN and EBOOT.BIN, and in the game's own script encoding as well: the
script uses a private encoding where a kanji is a two-byte code indexed off the glyph table,
so a string drawn through the same font would not appear as Shift-JIS at all.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
SYSDIR = ROOT / "iso_extract" / "PSP_GAME" / "SYSDIR"

PHRASES = ["最初から", "続きから", "データインストール", "設定",
           "物語を最初から始めます", "各種設定を行います", "START"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "title_strings.json")
    args = parser.parse_args()

    found = {}
    for name in ("BOOT.BIN", "EBOOT.BIN"):
        path = SYSDIR / name
        if not path.exists():
            continue
        data = path.read_bytes()
        print(f"{name}: {len(data)} bytes")
        for phrase in PHRASES:
            for label, encoded in (("sjis", phrase.encode("shift_jis", "ignore")),
                                   ("utf8", phrase.encode("utf-8")),
                                   ("utf16le", phrase.encode("utf-16-le"))):
                if not encoded:
                    continue
                at, hits = 0, []
                while len(hits) < 6:
                    at = data.find(encoded, at)
                    if at < 0:
                        break
                    hits.append(at)
                    at += 1
                if hits:
                    print(f"   {phrase!r} as {label}: {[hex(h) for h in hits]}")
                    found.setdefault(name, {}).setdefault(phrase, {})[label] = hits
        if name not in found:
            print("   none of the phrases appear in any of the three encodings")

    args.out.write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

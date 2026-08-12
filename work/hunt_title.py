"""Look for the title menu wording everywhere the disc keeps data, not just the executable.

`最初から` and `続きから` are not in BOOT.BIN -- all 71 occurrences of から there were read and
none of them is the menu.  But that search never left the executable, and the disc has eight
more data files, most of which are not LZ11 and so were never opened by the texture work.

から is two bytes in the engine's encoding.  Hiragana is one byte, `code = 0x8200 | (b + 0x77)`,
so か (SJIS 0x82A9) is 0x32 and ら (0x82E7) is 0x70.  Same for この and です, which pins the
startup disclaimer.  Every raw file is searched, and so is every LZ11 stream inside it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import lzss

ROOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME")


def kana(text: str) -> bytes:
    """Encode plain hiragana the way the engine stores it."""
    import codecs
    out = bytearray()
    for ch in text:
        sjis = codecs.encode(ch, "shift_jis")
        if len(sjis) != 2 or sjis[0] != 0x82:
            raise ValueError(f"not plain hiragana: {ch}")
        out.append(sjis[1] - 0x77)
    return bytes(out)


def sjis(text: str) -> bytes:
    return text.encode("shift_jis")


# Two bytes of the engine encoding turn up by accident everywhere, so the needles have to be
# long.  Both encodings are tried: the engine's private one for anything the script interpreter
# reads, and plain Shift-JIS in case the title screen's strings were never converted -- that
# would explain why searching the executable for から found 71 of them and none was the menu.
NEEDLES = {
    "ありません (engine)": kana("ありません"),
    "する (engine)": kana("するじんぶつ"),
    "きから (engine)": kana("きから"),
    "はじめから (engine)": kana("はじめから"),
    "つづきから (engine)": kana("つづきから"),
    "ものがたり (engine)": kana("ものがたり"),
    "してください (engine)": kana("してください"),
    "最初から (sjis)": sjis("最初から"),
    "続きから (sjis)": sjis("続きから"),
    "きから (sjis)": sjis("きから"),
    "この物語 (sjis)": sjis("この物語"),
    "フィクション (sjis)": sjis("フィクション"),
    "ください (sjis)": sjis("ください"),
    "データインストール (sjis)": sjis("データインストール"),
}


def streams(blob: bytes):
    at = 0
    while at < len(blob) - 4:
        if blob[at] == 0x11:
            size = int.from_bytes(blob[at + 1:at + 4], "little")
            if 1024 <= size <= 64 << 20:
                try:
                    plain, consumed = lzss.decompress(blob, at, limit=64 << 20)
                except Exception:
                    plain = None
                if plain is not None and len(plain) == size:
                    yield at, plain
                    at += max(consumed, 4)
                    continue
        at += 4


def count(blob: bytes, needle: bytes) -> list[int]:
    hits, at = [], blob.find(needle)
    while at >= 0:
        hits.append(at)
        at = blob.find(needle, at + 1)
    return hits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", nargs="*",
                        default=["USRDIR/0000", "USRDIR/0001", "USRDIR/0002", "USRDIR/0003",
                                 "USRDIR/0004", "USRDIR/0010", "USRDIR/0011", "USRDIR/0012",
                                 "SYSDIR/BOOT.BIN", "SYSDIR/EBOOT.BIN"])
    parser.add_argument("--context", type=int, default=0,
                        help="print this many bytes around each hit")
    args = parser.parse_args()

    targets = []
    for name in args.files:
        path = ROOT / name
        if not path.exists():
            continue
        blob = path.read_bytes()
        targets.append((name, blob))
        for offset, plain in streams(blob):
            targets.append((f"{name}@{offset:#x}", plain))

    print(f"{len(targets)} blobs searched\n")
    for label, needle in NEEDLES.items():
        print(f"=== {label}  ({needle.hex(' ')})")
        total = 0
        for name, blob in targets:
            hits = count(blob, needle)
            if hits:
                total += len(hits)
                print(f"   {name}: {len(hits)}x  first {hits[0]:#x}")
                if args.context:
                    for at in hits[:3]:
                        lo = max(0, at - args.context)
                        print(f"      {blob[lo:at + args.context].hex(' ')}")
        if not total:
            print("   nowhere")
        print()


if __name__ == "__main__":
    main()

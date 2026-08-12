"""Hunt for the title menu strings the earlier passes could not find.

最初から, 続きから, データインストール, 設定 and START are on screen, so they exist somewhere.
Three places have already been ruled out: no texture stream in any USRDIR file, no Shift-JIS,
UTF-8 or UTF-16 form of the words in either executable, and nothing in the script.

The gap in that search is that a PSP EBOOT is usually compressed.  ~PSP files carry a KL4E,
KL3E, 2RLZ or gzip payload and the plain text only appears once it is decoded, so grepping the
file as it sits on disc proves nothing about what is inside it.

So this looks at what each candidate actually is before searching it -- header, entropy and
how much of it is printable -- and reports rather than assumes.  Whatever holds those five
words has to be a file that is either compressed or not yet identified.
"""

from __future__ import annotations

import argparse
import json
import zlib
from collections import Counter
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
ISO = ROOT / "iso_extract"

WORDS = ["最初から", "続きから", "データインストール", "設定", "はじめから", "つづきから"]
ENCODINGS = ["shift_jis", "utf-8", "utf-16-le", "utf-16-be", "euc-jp", "cp932"]


def entropy(blob: bytes) -> float:
    if not blob:
        return 0.0
    counts = Counter(blob)
    total = len(blob)
    import math
    return -sum(n / total * math.log2(n / total) for n in counts.values())


def describe(path: Path) -> dict:
    head = path.read_bytes()[:64] if path.stat().st_size else b""
    blob = path.read_bytes()[:1 << 20]
    magic = head[:4]
    kind = "unknown"
    if magic == b"~PSP":
        kind = f"~PSP, inner tag {head[0x08:0x0c]!r}, attr {int.from_bytes(head[0x04:0x06], 'little'):#x}"
    elif magic == b"\x7fELF":
        kind = "ELF"
    elif magic[:2] == b"\x1f\x8b":
        kind = "gzip"
    elif magic == b"PSMF":
        kind = "PSMF video"
    elif magic == b"RIFF":
        kind = "RIFF"
    elif head[:8] == b"\x00PSF\x01\x01\x00\x00":
        kind = "SFO"
    return {"path": str(path.relative_to(ISO)), "size": path.stat().st_size,
            "magic": magic.hex(), "kind": kind,
            "entropy": round(entropy(blob), 2),
            "printable_ascii": round(sum(32 <= b < 127 for b in blob) / max(1, len(blob)), 3)}


def search(blob: bytes, label: str) -> list:
    hits = []
    for word in WORDS:
        for enc in ENCODINGS:
            try:
                needle = word.encode(enc)
            except UnicodeEncodeError:
                continue
            at = blob.find(needle)
            if at >= 0:
                hits.append({"where": label, "word": word, "encoding": enc, "offset": at})
    return hits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "title_hunt.json")
    args = parser.parse_args()

    files = sorted(p for p in ISO.rglob("*") if p.is_file())
    described, hits = [], []
    for path in files:
        info = describe(path)
        described.append(info)
        blob = path.read_bytes()
        hits += search(blob, info["path"])
        # a gzip member can start anywhere; try the obvious ones
        if info["kind"].startswith("~PSP") or info["kind"] == "gzip":
            for start in range(0, min(len(blob), 4096)):
                if blob[start:start + 2] == b"\x1f\x8b":
                    try:
                        plain = zlib.decompress(blob[start:], 47)
                    except zlib.error:
                        continue
                    info["gzip_at"] = start
                    info["inflated"] = len(plain)
                    hits += search(plain, info["path"] + " (inflated)")
                    break

    args.out.write_text(json.dumps({"schema": "enkaku_title_hunt_v1",
                                    "files": described, "hits": hits},
                                   ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(files)} files examined\n")
    print(f"{'file':44s} {'size':>10s}  {'H':>5s} {'ascii':>6s}  kind")
    for info in described:
        if info["size"] < 4096:
            continue
        print(f"{info['path']:44s} {info['size']:10d}  {info['entropy']:5.2f} "
              f"{info['printable_ascii']:6.3f}  {info['kind']}"
              + (f"  gzip@{info['gzip_at']} -> {info['inflated']}" if "gzip_at" in info else ""))
    print(f"\n{len(hits)} hits for the title words")
    for h in hits[:20]:
        print(f"   {h['where']}  {h['word']}  as {h['encoding']}  at {h['offset']:#x}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

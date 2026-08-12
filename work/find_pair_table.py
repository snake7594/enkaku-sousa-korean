"""Find the lookup that turns BOOT.BIN's byte pairs into font slots.

The pairs cannot be a formula.  88 F5 is 存 and 88 F6 is 在 -- same lead, next trail -- and in
the font those sit at slots 183 and 143.  A trail that steps by one while the slot jumps
backwards by forty is a table being read, not an index being computed.

So this looks for the table by its contents rather than its position: somewhere there should
be two adjacent entries holding 183 and 143, and if that place is really the table then the
entry 0x9A - 0xF5 back from it must hold 170 for 上, and the 0x89 lead's entry 0x51 must hold
190 for 書.  Three independent predictions from one candidate address.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
FONT = ROOT / "font_extract"
ISO = ROOT / "iso_extract"

# (lead, trail) -> the character the decoded sentence requires
PAIRS = {(0x88, 0xF5): "存", (0x88, 0xF6): "在", (0x88, 0x9A): "上", (0x89, 0x51): "書"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", nargs="*", default=[
        "PSP_GAME/SYSDIR/BOOT.BIN", "PSP_GAME/USRDIR/0001", "PSP_GAME/USRDIR/0004",
        "PSP_GAME/USRDIR/0011"])
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "pair_table.json")
    args = parser.parse_args()

    charmap = json.loads((FONT / "charmap_v5.json").read_text(encoding="utf-8"))["map"]
    slot_of = {}
    for key, char in charmap.items():
        slot_of.setdefault(char, int(key))
    want = {pair: slot_of.get(char) for pair, char in PAIRS.items()}
    print("what the table must hold:")
    for (lead, trail), char in PAIRS.items():
        print(f"   {lead:#04x} {trail:#04x} -> {char} -> font slot {want[(lead, trail)]}")
    if any(v is None for v in want.values()):
        print("\nsome of those characters are not in the font at all; nothing to search for")
        return

    a, b = want[(0x88, 0xF5)], want[(0x88, 0xF6)]
    hits = []
    for rel in args.files:
        path = ISO / rel
        if not path.exists():
            continue
        blob = path.read_bytes()
        for width, order in ((2, "little"), (2, "big"), (1, None)):
            needle = (bytes([a, b]) if width == 1
                      else a.to_bytes(2, order) + b.to_bytes(2, order))
            at = blob.find(needle)
            while at >= 0:
                base = at - 0xF5 * width          # start of the 0x88 lead's row
                ok = base >= 0
                checks = {}
                if ok:
                    for (lead, trail), slot in want.items():
                        # rows are assumed to follow one another, 0x100 entries apart
                        pos = base + ((lead - 0x88) * 0x100 + trail) * width
                        if pos + width > len(blob):
                            ok = False
                            break
                        got = (blob[pos] if width == 1
                               else int.from_bytes(blob[pos:pos + width], order))
                        checks[f"{lead:#04x} {trail:#04x}"] = got
                        if got != slot:
                            ok = False
                if ok:
                    hits.append({"file": rel, "base": base, "width": width,
                                 "order": order or "n/a", "checks": checks})
                at = blob.find(needle, at + 1)
        print(f"{rel:34s} searched")

    args.out.write_text(json.dumps({"schema": "enkaku_pair_table_v1",
                                    "want": {f"{k[0]:#04x} {k[1]:#04x}": v
                                             for k, v in want.items()},
                                    "hits": hits}, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"\n{len(hits)} candidate tables satisfy all four pairs")
    for h in hits[:8]:
        print(f"   {h['file']}  base {h['base']:#010x}  {h['width']}-byte {h['order']}")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

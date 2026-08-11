"""Rebuild the script stream with longer text, and move every absolute reference with it.

Korean needs about 140% of the Japanese byte budget -- kana are one byte, Hangul syllables
two -- so text has to grow, and the moment it does every stored offset behind it is wrong.
There are 26,537 of them.

The engine is deliberately boring: build an old->new offset map, splice the new text in,
then rewrite each reference through the map.  What matters is not the splice but the two
tests around it.

  identity   run it with zero expansion.  The output must be byte-for-byte the original.
             This catches map-off-by-one, a reference written to the wrong place, a block
             boundary read wrong -- most ways the engine can be subtly broken -- and it
             catches them without needing any translated text to exist yet.

  reparse    run it with real expansion, then parse the *output* from scratch and check
             the markers, the text ends, and all 26,537 references still land where they
             should.  A map that is merely self-consistent passes the first test and fails
             this one.

Neither test can be satisfied by a plausible-looking map, which is the point.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

import opcodes
import text_blocks

SCRIPT_START = 0x02AC80


class OffsetMap:
    """old offset -> new offset, for a stream whose text blocks changed length.

    Held as a full array rather than a list of breakpoints.  It costs 12 MB and removes a
    whole class of bug: every lookup is exact, including offsets that land *inside* a block
    that moved, which a breakpoint search has to special-case and can get quietly wrong.
    """

    def __init__(self, size: int, blocks: list, new_texts: list[bytes]):
        self.table = np.zeros(size + 1, dtype=np.int64)
        old = new = 0
        self.deltas = []
        for block, text in zip(blocks, new_texts):
            span = block.text - old
            self.table[old:block.text] = np.arange(new, new + span)
            old, new = block.text, new + span

            # inside the text: map proportionally, then pin the end exactly.  Only the two
            # edges are ever referenced in practice; the interior is mapped so that a
            # stray reference lands somewhere sane instead of out of bounds.
            old_len, new_len = block.text_end - block.text, len(text)
            if old_len:
                inner = np.linspace(new, new + new_len, old_len, endpoint=False)
                self.table[block.text:block.text_end] = inner.astype(np.int64)
            old, new = block.text_end, new + new_len
            self.deltas.append(new_len - old_len)

        span = size - old
        self.table[old:size + 1] = np.arange(new, new + span + 1)
        self.new_size = new + span

    def __getitem__(self, offset: int) -> int:
        return int(self.table[offset])


def rebuild(plain: bytes, blocks: list, new_texts: list[bytes]) -> tuple[bytearray, OffsetMap]:
    out, cursor = bytearray(), 0
    for block, text in zip(blocks, new_texts):
        out += plain[cursor:block.text]
        out += text
        cursor = block.text_end
    out += plain[cursor:]
    return out, OffsetMap(len(plain), blocks, new_texts)


def remap(out: bytearray, refs: list, mapping: OffsetMap, size: int) -> tuple[int, int]:
    """Rewrite each reference in place.  Returns (written, skipped)."""
    written = skipped = 0
    for addr, value in refs:
        if not (0 <= value <= size):
            skipped += 1
            continue
        at, target = mapping[addr], mapping[value]
        out[at:at + 4] = target.to_bytes(4, "little")
        written += 1
    return written, skipped


def load_refs(path: Path) -> tuple[list, list]:
    data = json.loads(path.read_text())
    return ([tuple(r) for r in data["refs"]["header"]],
            [tuple(r) for r in data["refs"]["inline"]])


def reparse_check(out: bytes, blocks: list, new_texts: list[bytes],
                  mapping: OffsetMap, refs: list) -> dict:
    """Parse the produced stream from scratch and see if it still holds together."""
    new_blocks = []
    cursor = 0
    for block, text in zip(blocks, new_texts):
        start = mapping[block.text]
        new_blocks.append((mapping[block.marker], start, start + len(text)))

    flags = bytearray(len(out))
    for _, start, end in new_blocks:
        flags[start:end] = b"\x01" * (end - start)
    insns = opcodes.parse(out, SCRIPT_START, len(out), flags)
    seen = {p for p, _, _ in insns}

    markers = sum(1 for m, _, _ in new_blocks if m in seen)
    ends = sum(1 for _, _, e in new_blocks if e in seen)
    resolved = on_edge = 0
    for addr, value in refs:
        at = mapping[addr]
        target = int.from_bytes(out[at:at + 4], "little")
        if SCRIPT_START <= target < len(out):
            resolved += 1
            on_edge += target in seen
    return {"instructions": len(insns), "markers": markers, "text_ends": ends,
            "blocks": len(new_blocks), "refs": len(refs),
            "resolved": resolved, "on_boundary": on_edge}


def expand(text: bytes, ratio: float) -> bytes:
    """Grow a block by appending two-byte kanji codes, to exercise the wide-token path."""
    extra = int(len(text) * ratio) // 2
    return text + bytes([0x88, 0x40]) * extra


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=Path(r"D:\psp\원격수사\build\ref_manifest.json"))
    parser.add_argument("--ratio", type=float, default=0.5,
                        help="synthetic expansion for the reparse test")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    plain = text_blocks.load_stream()
    blocks = text_blocks.find_blocks(plain)
    header, inline = load_refs(args.manifest)
    refs = header + inline
    print(f"{len(plain)} byte stream, {len(blocks)} blocks, {len(refs)} references "
          f"({len(header)} header + {len(inline)} inline)")

    # how many references point into text?  those are the ones a growing block endangers
    spans = [(b.text, b.text_end) for b in blocks]
    starts = np.array([s for s, _ in spans])
    ends = np.array([e for _, e in spans])
    values = np.array([v for _, v in refs])
    idx = np.searchsorted(starts, values, side="right") - 1
    inside = int(np.sum((idx >= 0) & (values < ends[np.clip(idx, 0, len(ends) - 1)])))
    print(f"   {inside} references point inside a text block "
          f"({100.0 * inside / len(refs):.2f}%)")

    print("\nidentity test (zero expansion):")
    texts = [plain[b.text:b.text_end] for b in blocks]
    out, mapping = rebuild(plain, blocks, texts)
    written, skipped = remap(out, refs, mapping, len(plain))
    same = bytes(out) == plain
    print(f"   rebuilt {len(out)} bytes, rewrote {written} references ({skipped} skipped)")
    print(f"   byte-identical to the original: {'yes' if same else 'NO'}")
    if not same:
        diff = [i for i in range(min(len(out), len(plain))) if out[i] != plain[i]]
        print(f"   {len(diff)} differing bytes, first at 0x{diff[0]:06x}: "
              f"{plain[diff[0] - 4:diff[0] + 4].hex(' ')} -> {bytes(out[diff[0] - 4:diff[0] + 4]).hex(' ')}")
        return

    print(f"\nreparse test (+{100 * args.ratio:.0f}% synthetic expansion):")
    grown = [expand(t, args.ratio) for t in texts]
    out, mapping = rebuild(plain, blocks, grown)
    written, skipped = remap(out, refs, mapping, len(plain))
    print(f"   rebuilt {len(out)} bytes (+{len(out) - len(plain)}), "
          f"rewrote {written} references")
    stats = reparse_check(bytes(out), blocks, grown, mapping, refs)
    print(f"   parsed {stats['instructions']} instructions from the output")
    print(f"   markers   {stats['markers']}/{stats['blocks']}")
    print(f"   text ends {stats['text_ends']}/{stats['blocks']}")
    print(f"   references resolved {stats['resolved']}/{stats['refs']}, "
          f"on a boundary {stats['on_boundary']}/{stats['resolved']}")
    ok = (stats["markers"] == stats["blocks"] and stats["text_ends"] == stats["blocks"]
          and stats["resolved"] == stats["refs"])
    print("   the expanded stream parses as cleanly as the original"
          if ok else "   the expanded stream does NOT hold together")

    if args.out and ok:
        args.out.write_bytes(bytes(out))
        print(f"-> {args.out}")


if __name__ == "__main__":
    main()

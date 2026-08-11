"""Settle the `01 <u32>` question and emit the reference manifest a reflow will rewrite.

The walk cannot decide this one.  Reading `01` as one byte and reading it as five both
land on all 26,466 checkpoints, because after diverging the two parses re-converge a few
bytes later -- so "the walk passes" is not evidence here, and it would have been easy to
mistake it for some.

Two things do decide it, and neither depends on the walk:

  completeness  if `01` is a five-byte command, then essentially *every* `01` at an
                instruction boundary outside text should carry a valid in-script target.
                A form that only works 60% of the time is not the form.

  target bias   a real reference set points at labels, so the byte at the target should
                look nothing like the stream at large.  Coincidences inherit the stream's
                own byte distribution.  This is measured as a likelihood ratio rather than
                asserted.

The manifest it writes -- header pointers, tail table records, inline references -- is the
complete set of absolute offsets that must be remapped when text grows.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

import opcodes
import text_blocks

SCRIPT_START = 0x02AC80
FONT = (0x80, 0x80 + 175104)


def membership(plain: bytes, blocks: list) -> bytearray:
    flags = bytearray(len(plain))
    for block in blocks:
        flags[block.text:block.text_end] = b"\x01" * (block.text_end - block.text)
    return flags


def canonical_walk(plain: bytes, start: int, stop: int, flags: bytearray) -> list:
    """The parse we are adopting: `01` is a five-byte reference unless it is inside text."""
    out, pos, in_ruby = [], start, False
    while pos < stop:
        code = plain[pos]
        wide = ({opcodes.REF, opcodes.LITERAL} if opcodes.WIDE_LITERAL
                else {opcodes.REF})
        if code in wide and not flags[pos] and pos + 5 <= stop:
            out.append((pos, code, 5))
            pos += 5
        else:
            nxt, in_ruby = opcodes.step(plain, pos, in_ruby)
            out.append((pos, code, nxt - pos))
            pos = nxt
    return out


def log_ratio(targets: Counter, background: Counter, total_bg: int) -> float:
    """log10 likelihood ratio: targets drawn from labels vs drawn from the stream at large."""
    total = sum(targets.values())
    score = 0.0
    for byte, count in targets.items():
        p_obs = count / total
        p_bg = max(background.get(byte, 0), 1) / total_bg
        score += count * math.log10(p_obs / p_bg)
    return score


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path,
                        default=Path(r"D:\psp\원격수사\build\ref_manifest.json"))
    args = parser.parse_args()

    plain = text_blocks.load_stream()
    blocks = text_blocks.find_blocks(plain)
    size = len(plain)
    flags = membership(plain, blocks)

    # walk to the end of the stream, not to the last text block.  The bytes past the
    # record table looked like a tail but parse as script and carry at least one plain
    # `01 95 ac 02 00` -> 0x02AC95, so stopping early would have dropped real references.
    script_end = size
    insns = canonical_walk(plain, SCRIPT_START, script_end, flags)
    boundary = {p for p, _, _ in insns} | {script_end}
    print(f"canonical parse: {len(insns)} instructions over "
          f"0x{SCRIPT_START:06x}-0x{script_end:06x}")
    hit = sum(1 for b in blocks for c in (b.marker, b.text_end) if c in boundary)
    print(f"   {hit}/{2 * len(blocks)} block checkpoints hit "
          f"(marker and text end; `end+2` was never a boundary -- `12 10 <u32>` is one "
          f"six-byte instruction, not a two-byte marker)")

    # completeness: of every `01` command the parse emits, how many resolve?
    ones = [(p, int.from_bytes(plain[p + 1:p + 5], "little"))
            for p, code, size_ in insns if code == opcodes.REF and size_ == 5]
    # Only the regions that actually hold script.  Profiling the sections the header marks
    # out showed `01 <u32>` resolving at 80-87% inside them and at 0-37% outside, so the
    # sites outside are coincidences -- and rewriting four bytes at a coincidence destroys a
    # real instruction.  0x16EFB8 onward is the clearest case: 469 candidates, none of which
    # resolve, all of them previously rewritten.
    SCRIPT_REGIONS = ((0x037060, 0x169A70), (0x169D80, 0x16EFB8))
    in_script = lambda p: any(lo <= p < hi for lo, hi in SCRIPT_REGIONS)
    before = len(ones)
    ones = [(p, v) for p, v in ones if in_script(p)]
    print(f"   {before - len(ones)} candidates outside the script regions dropped")
    valid = [(p, v) for p, v in ones if SCRIPT_START <= v < script_end]
    on_edge = [(p, v) for p, v in valid if v in boundary]
    print(f"\ncompleteness: {len(ones)} `01` commands outside text")
    print(f"   {len(valid)} have an in-script target ({100.0 * len(valid) / len(ones):.2f}%)")
    print(f"   {len(on_edge)} of those land on an instruction boundary "
          f"({100.0 * len(on_edge) / len(valid):.2f}%)")
    stray = [(p, v) for p, v in ones if not (SCRIPT_START <= v < script_end)]
    if stray:
        print(f"   {len(stray)} do not resolve, e.g. "
              f"{[(f'0x{p:06x}', f'0x{v:08x}') for p, v in stray[:4]]}")

    # target bias, against the stream's own byte distribution
    background = Counter(plain[SCRIPT_START:script_end])
    total_bg = script_end - SCRIPT_START
    targets = Counter(plain[v] for _, v in valid)
    print(f"\ntarget bias: {len(set(v for _, v in valid))} distinct targets")
    for byte, count in targets.most_common(6):
        share = 100.0 * count / len(valid)
        base = 100.0 * background[byte] / total_bg
        print(f"   {byte:02x}: {share:5.1f}% of targets vs {base:4.1f}% of the stream "
              f"({share / base:6.1f}x)")
    print(f"   log10 likelihood ratio vs the stream's own distribution: "
          f"{log_ratio(targets, background, total_bg):,.0f}")

    # the other two reference sets
    header = [(a, int.from_bytes(plain[a:a + 4], "little")) for a in range(0, 0x80, 4)]
    header = [(a, v) for a, v in header if SCRIPT_START <= v < script_end]
    # the `01 <u32>` record run that follows the last text block.  It is inside the walked
    # range now, so parse it separately and check the walk found it rather than assuming.
    table, at = [], blocks[-1].end + 4
    while at + 5 <= size and plain[at] == 0x01:
        table.append((at + 1, int.from_bytes(plain[at + 1:at + 5], "little")))
        at += 5
    inline_at = {p + 1 for p, _ in valid}
    covered = sum(1 for a, _ in table if a in inline_at)
    print(f"\nheader pointers: {len(header)}   record run: {len(table)} entries "
          f"0x{blocks[-1].end + 4:06x}-0x{at:06x}")
    print(f"   {covered}/{len(table)} of them were already found by the walk"
          + ("" if covered == len(table) else "  <-- the rest are added explicitly"))

    extra = [(a, v) for a, v in table if a not in inline_at
             and SCRIPT_START <= v < script_end]
    valid = valid + [(a - 1, v) for a, v in extra]
    total = len(header) + len(valid)
    print(f"\nmanifest: {total} absolute references to remap "
          f"({len(header)} header + {len(valid)} in-stream)")

    args.out.write_text(json.dumps({
        "layout": {"font": list(FONT), "script": [SCRIPT_START, script_end],
                   "record_run": [blocks[-1].end + 4, at], "size": size},
        "parse": {"instructions": len(insns), "checkpoints": f"{hit}/{2 * len(blocks)}"},
        "refs": {"header": [[a, v] for a, v in header],
                 "inline": [[p + 1, v] for p, v in valid]},
        "unresolved": [[p, v] for p, v in stray],
    }, indent=1), encoding="utf-8")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

"""Walk the script stream with the interpreter's own length rule and see if it stays in step.

The rule lives in opcodes.py; this is the experiment that decides whether to trust it.
Three tests, each strictly harder than the last:

  text layer     from a block's first text byte, land exactly on its `12 10`
  command layer  from a block's end, land exactly on the next `07 1C`
  continuous     one walk from the first marker to the last block, never re-synchronised

The first two re-align at every block, so a rule that drifts only occasionally still scores
well; they are useful for *locating* a fault, not for clearing the rule.  The third is the
one that matters: a single wrong length anywhere throws the rest of the walk off by that
many bytes and every later checkpoint misses.  Reflow is only safe if the third passes.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import opcodes
import text_blocks


def walk(plain: bytes, start: int, target: int) -> tuple[bool, int, list]:
    """Walk from `start`; report whether we land on `target` exactly.

    The trace keeps the last few steps -- enough to see what the walk was doing when it
    went wrong, without carrying the whole path around.
    """
    pos, in_ruby = start, False
    trace: list[tuple[int, int, int]] = []
    while pos < target:
        before = pos
        pos, in_ruby = opcodes.step(plain, pos, in_ruby)
        trace.append((before, plain[before], pos - before))
        if len(trace) > 6:
            trace.pop(0)
        if pos <= before:                      # a zero-length step would spin forever
            return False, before, trace
    return pos == target, pos, trace


def report(name: str, results: list, plain: bytes, show: int) -> tuple[int, int]:
    hits = sum(1 for ok, *_ in results if ok)
    total = len(results)
    print(f"\n{name}: {hits}/{total} exact ({100.0 * hits / total if total else 0:.2f}%)")
    if hits == total:
        return hits, total

    misses = [r for r in results if not r[0]]
    print("   overshoot (bytes past target): "
          f"{dict(sorted(Counter(l - t for _, l, t, _ in misses).items())[:8])}")
    blame = Counter(tr[-1][1] for *_, tr in misses if tr)
    print(f"   code under the last step: {[(f'0x{c:02x}', n) for c, n in blame.most_common(6)]}")
    for _, landing, target, trace in misses[:show]:
        print(f"\n   miss: landed 0x{landing:06x}, wanted 0x{target:06x}")
        for addr, code, size in trace:
            print(f"      0x{addr:06x}  {code:02x}  +{size}  [{plain[addr:addr + size].hex()}]")
    return hits, total


def continuous(plain: bytes, blocks: list, show: int) -> tuple[int, int]:
    """One unbroken walk; every block edge is a checkpoint it must land on."""
    start, stop = blocks[0].marker, blocks[-1].end
    seen = opcodes.boundaries(plain, start, stop)

    checkpoints = []
    for block in blocks:
        checkpoints += [(block.marker, "07 1C"), (block.text_end, "12 10"), (block.end, "end")]
    checkpoints = [c for c in checkpoints if start <= c[0] <= stop]

    missed = [c for c in checkpoints if c[0] not in seen]
    hits = len(checkpoints) - len(missed)
    print(f"\ncontinuous walk 0x{start:06x} -> 0x{stop:06x} "
          f"({stop - start} bytes, {len(seen)} instructions)")
    print(f"   checkpoints hit: {hits}/{len(checkpoints)} "
          f"({100.0 * hits / len(checkpoints):.2f}%)")
    if missed:
        print(f"   first misses: {[(f'0x{o:06x}', k) for o, k in missed[:6]]}")
        first = missed[0][0]
        near = sorted(b for b in seen if abs(b - first) <= 16)
        print(f"   boundaries near 0x{first:06x}: {[f'0x{b:06x}' for b in near]}")
        print(f"   bytes: {plain[first - 12:first + 12].hex(' ')}")
    return hits, len(checkpoints)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show", type=int, default=3, help="misses to print in full")
    parser.add_argument("--raw-finder", action="store_true",
                        help="skip the finder's instruction-boundary check on `12 10`")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    plain = text_blocks.load_stream()
    blocks = text_blocks.find_blocks(plain, validate=not args.raw_finder)
    print(f"{len(plain)} byte stream, {len(blocks)} text blocks")

    text_results = []
    for b in blocks:
        ok, landing, trace = walk(plain, b.text, b.text_end)
        text_results.append((ok, landing, b.text_end, trace))

    cmd_results = []
    for b, nxt in zip(blocks, blocks[1:]):
        ok, landing, trace = walk(plain, b.end, nxt.marker)
        cmd_results.append((ok, landing, nxt.marker, trace))

    t_hit, t_tot = report("text layer    (block start -> 12 10)", text_results, plain, args.show)
    c_hit, c_tot = report("command layer (block end -> next 07 1C)", cmd_results, plain, args.show)
    k_hit, k_tot = continuous(plain, blocks, args.show)

    clean = t_hit == t_tot and c_hit == c_tot and k_hit == k_tot
    print(f"\nverdict: text {t_hit}/{t_tot}, commands {c_hit}/{c_tot}, continuous {k_hit}/{k_tot}")
    print("the rule walks the whole stream without desyncing -- reflow is safe to build"
          if clean else "the rule desyncs; reflow on this table would corrupt the script")

    if args.out:
        args.out.write_text(json.dumps({
            "clean": clean,
            "text": {"hit": t_hit, "total": t_tot},
            "command": {"hit": c_hit, "total": c_tot},
            "continuous": {"hit": k_hit, "total": k_tot},
            "table": {f"{k:02x}": v for k, v in sorted(opcodes.TABLE.items())},
            "terminators": [f"{c:02x}" for c in sorted(opcodes.TERMINATORS)],
        }, indent=1), encoding="utf-8")
        print(f"-> {args.out}")


if __name__ == "__main__":
    main()

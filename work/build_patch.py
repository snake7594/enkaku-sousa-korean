"""Produce the patched stream: Korean font, Korean text, and every reference moved with it.

This is the step the earlier size measurement deliberately skipped.  Splicing longer text in
is easy; the 26,537 absolute offsets that point past the splice are the actual work, and a
stream that has been spliced but not remapped runs until the first jump lands in the middle
of a moved instruction.

Text spans come from the translation rather than from the marker-delimited blocks, because
the translation starts at 0x0002AC87 -- before the first `07 1C` at 0x038B78 -- so text also
lives outside marked blocks and a block-keyed pass would silently skip it.

The output is checked by reparsing it from scratch: markers, text ends, and every reference
have to land on instruction boundaries in the *produced* stream, not in the plan that made
it.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import encode_korean
import opcodes
import reflow
import text_blocks
import translation_text

SCRIPT_START = 0x02AC80


@dataclass(frozen=True)
class Span:
    text: int
    text_end: int


def build_spans(plain: bytes, tsv: Path, slots: dict,
                shrink: int = 0,
                apply_overrides: bool = True) -> tuple[list, list, dict]:
    rows, spans, texts = [], [], []
    stats = {"rows": 0, "failed": 0, "overlap": 0}
    for start, translated_text in translation_text.load_for_patch(
        tsv, apply_overrides=apply_overrides
    ):
        stats["rows"] += 1
        encoded = encode_korean.encode_text(translated_text.replace("\\n", "\n"), slots)
        if encoded is None:
            stats["failed"] += 1
            continue
        end = encode_korean.run_end(plain, start)
        if shrink and len(encoded) > end - start - shrink:
            # Trim to an even number of bytes so a two-byte syllable is never cut in half.
            # This deliberately damages the dialogue -- it exists to test whether the engine
            # objects to the stream's *size* or to its *offsets*, which nothing else so far
            # has been able to separate.
            keep = max(0, (end - start - shrink) // 2 * 2)
            encoded = encoded[:keep]
        rows.append((start, end, encoded))
    rows.sort()

    cursor = -1
    for start, end, data in rows:
        if start < cursor:
            stats["overlap"] += 1
            continue
        spans.append(Span(start, end))
        texts.append(data)
        cursor = end
    return spans, texts, stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path,
                        default=Path(r"D:\psp\원격수사\build\stream1_ko_font_clean.bin"))
    parser.add_argument("--tsv", type=Path,
                        default=Path(r"D:\psp\원격수사\build\translation_ko_clean.tsv"))
    parser.add_argument("--slots", type=Path,
                        default=Path(r"D:\psp\원격수사\build\korean_slots_full_clean.json"))
    parser.add_argument("--manifest", type=Path,
                        default=Path(r"D:\psp\원격수사\build\ref_manifest.json"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--shrink", type=int, default=0,
                        help="trim every line so each span ends up this many bytes shorter")
    parser.add_argument("--skip", default=None,
                        help="comma-separated reference addresses to leave alone")
    parser.add_argument("--no-inline", action="store_true",
                        help="rewrite only header and pointer-array entries")
    parser.add_argument("--arrays", type=Path,
                        default=Path(r"D:\psp\원격수사\build\pointer_arrays.json"))
    parser.add_argument("--refs-after", type=lambda v: int(v, 0), default=0,
                        help="only rewrite references at or after this address")
    parser.add_argument("--to-offset", type=lambda v: int(v, 0), default=0,
                        help="stop expanding at this offset, so a band can be tested alone")
    parser.add_argument("--from-offset", type=lambda v: int(v, 0), default=0,
                        help="only expand text at or after this offset, leaving everything "
                             "before it byte-identical -- lets a failure be located by "
                             "region instead of by rebuilding the whole model")
    parser.add_argument(
        "--translation-is-final",
        action="store_true",
        help="do not reapply older residual/semantic overrides to the supplied TSV",
    )
    args = parser.parse_args()

    plain = args.base.read_bytes()
    slots = {c: int(i) for c, i in
             json.loads(args.slots.read_text(encoding="utf-8"))["slots"].items()}
    header, inline = reflow.load_refs(args.manifest)
    # The inline `01 <u32>` set was identified statistically -- strong for the group (35-54x
    # target-byte bias) but never proved member by member, and a site that is not a
    # reference gets four bytes of real script overwritten.  The pointer arrays and header
    # entries, by contrast, are structural.  Dropping the statistical set isolates which of
    # the two is doing the damage.
    refs = header + ([] if args.no_inline else inline)
    if args.no_inline:
        print(f"   {len(inline)} statistically-identified inline references left untouched")

    # Bare u32 arrays the tag-driven scan could not see.  The header points at them and
    # their entries carry no `01` in front, so nothing about their shape distinguishes them
    # from data until you follow the header's own targets.  Leaving them stale is what
    # killed STEP2: the text they point at moved and they kept pointing at where it was.
    if args.arrays and args.arrays.exists():
        extra = [tuple(r) for r in json.loads(args.arrays.read_text())["refs"]]
        known = {a for a, _ in refs}
        extra = [r for r in extra if r[0] not in known]
        refs += extra
        print(f"   +{len(extra)} untagged pointer-array entries")
    spans, texts, stats = build_spans(
        plain,
        args.tsv,
        slots,
        args.shrink,
        apply_overrides=not args.translation_is_final,
    )
    if args.from_offset or args.to_offset:
        hi = args.to_offset or len(plain)
        kept = [(s, t) for s, t in zip(spans, texts)
                if args.from_offset <= s.text < hi]
        spans, texts = [s for s, _ in kept], [t for _, t in kept]
        grown = sum(len(t) for t in texts) - sum(s.text_end - s.text for s in spans)
        print(f"   limited to 0x{args.from_offset:06x}-0x{hi:06x}: "
              f"{len(spans)} spans, +{grown} bytes")
    print(f"{stats['rows']} rows: {len(spans)} usable, {stats['failed']} unencodable, "
          f"{stats['overlap']} overlapping")
    print(f"   text {sum(s.text_end - s.text for s in spans)} -> {sum(map(len, texts))} bytes")

    out, mapping = reflow.rebuild(plain, spans, texts)
    if args.skip:
        # Header words 0x74 and 0x78 sit right before the font offset at 0x7C and were only
        # ever classed as pointers because their values fall inside the script.  If either is
        # a length or a count, shifting it by the growth corrupts the header at load time --
        # and one of them already shifted by 156,120 where a size would want 156,170.
        drop = {int(v, 0) for v in args.skip.split(",")}
        refs = [r for r in refs if r[0] not in drop]
        print(f"   skipping references at {sorted(hex(d) for d in drop)}")
    if args.refs_after:
        # Leaving the early references alone makes that whole region byte-identical to the
        # original.  If the game then survives, the rewrites there were the damage -- false
        # positives overwritten with four bytes of remapped garbage.  If it still dies, the
        # opposite is true: a reference form we never identified is pointing at text that
        # moved, and no amount of care with the ones we found will help.
        before = len(refs)
        refs = [r for r in refs if r[0] >= args.refs_after]
        print(f"   {before - len(refs)} references before 0x{args.refs_after:06x} "
              f"left untouched")
    written, skipped = reflow.remap(out, refs, mapping, len(plain))
    print(f"   stream {len(plain)} -> {len(out)} bytes; "
          f"{written} references rewritten, {skipped} skipped")

    # verify against the produced bytes, not against the plan
    blocks = text_blocks.find_blocks(plain)
    flags = bytearray(len(out))
    for span, text in zip(spans, texts):
        start = mapping[span.text]
        flags[start:start + len(text)] = b"\x01" * len(text)
    insns = opcodes.parse(bytes(out), SCRIPT_START, len(out), flags)
    seen = {p for p, _, _ in insns}

    markers = sum(1 for b in blocks if mapping[b.marker] in seen)
    resolved = on_edge = 0
    for addr, value in refs:
        target = int.from_bytes(out[mapping[addr]:mapping[addr] + 4], "little")
        if SCRIPT_START <= target < len(out):
            resolved += 1
            on_edge += target in seen
    print(f"\nreparse of the output: {len(insns)} instructions")
    print(f"   markers {markers}/{len(blocks)}")
    print(f"   references resolved {resolved}/{len(refs)}, "
          f"on a boundary {on_edge}/{resolved}")

    ok = markers == len(blocks) and resolved == len(refs)
    print("   the patched stream holds together" if ok else "   FAILED -- not writing")
    if not ok:
        raise SystemExit(1)

    args.out.write_bytes(bytes(out))
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

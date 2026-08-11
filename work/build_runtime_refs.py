"""Rebuild the translated stream with interpreter references remapped.

The scene interpreter has several absolute-reference forms: ``01 <u32>`` calls,
``0A/0B <u32>`` jumps, and ``0C/0D <typed-condition><u32>`` branches.  A linear byte
scan can mistake an ``01`` inside one of those operands for a second reference and
overwrite the real operand.  This script follows recovered instruction boundaries,
filters contradictory manifest entries, and then rewrites all references through the
text-growth map.  The output is a separate candidate stream; the emulator is deliberately
not launched by this tool.
"""

from __future__ import annotations

import argparse
import json
from bisect import bisect_right
from pathlib import Path

import build_patch
import opcodes
import ref_manifest
import reflow
import text_blocks

SCRIPT_START = 0x02AC80
FONT_TABLE_START = 0x80
FONT_TABLE_TILES = 684
FONT_TABLE_END = FONT_TABLE_START + FONT_TABLE_TILES * 256

ROOT = Path(r"D:\psp\원격수사")
ORIGINAL_STREAM = ROOT / "font_extract" / "script_stream.bin"
BASE_STREAM = ROOT / "build" / "stream1_ko_font_clean.bin"
TSV = ROOT / "build" / "translation_ko_clean.tsv"
SLOTS = ROOT / "build" / "korean_slots_full_clean.json"
MANIFEST = ROOT / "build" / "ref_manifest.json"
ARRAYS = ROOT / "build" / "pointer_arrays.json"
OPCODE_TABLE = ROOT / "build" / "opcode_table.json"
REFERENCE_CORRECTIONS = ROOT / "build" / "runtime_reference_supplement_cfg17.json"

# These four short runs were admitted by the broad pointer-array scan because
# their packed 16-bit fields happen to form in-range u32 values.  They are
# resource/record data, not stream addresses (for example 01 00 12 00), so
# reflowing them would corrupt state values.  Keep the original scan artifact
# untouched, but do not treat these ranges as runtime pointers.
POINTER_ARRAY_DATA_RANGES = (
    (0x73804, 0x73810),
    (0x7883A, 0x78846),
    (0x16FC24, 0x16FC30),
    (0x16FD5C, 0x16FD68),
)


def load_pointer_array_refs() -> list[tuple[int, int]]:
    if not ARRAYS.exists():
        return []
    raw = [tuple(item) for item in
           json.loads(ARRAYS.read_text(encoding="utf-8"))["refs"]]
    return [(addr, value) for addr, value in raw
            if not any(start <= addr < end
                       for start, end in POINTER_ARRAY_DATA_RANGES)]


def load_reference_corrections(path: Path | None
                               ) -> tuple[list[tuple[int, int]], set[int], dict]:
    """Load reference additions/removals proven by the user-tested CFG17 stream."""
    if path is None or not path.exists():
        return [], set(), {
            "reference_corrections": str(path) if path else None,
            "supplemental_refs_requested": 0,
            "excluded_ref_addresses_requested": 0,
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    supplemental = [tuple(item) for item in payload.get("refs", [])]
    excluded = {int(address) for address in payload.get("exclude_addresses", [])}
    if len({address for address, _ in supplemental}) != len(supplemental):
        raise ValueError(f"duplicate supplemental reference address in {path}")
    if any(address in excluded for address, _ in supplemental):
        raise ValueError(f"reference correction both adds and excludes an address in {path}")
    verification = payload.get("verification", {})
    if verification and not verification.get("reproduces_working_stream_exactly", False):
        raise ValueError(f"unverified reference correction file: {path}")
    return supplemental, excluded, {
        "reference_corrections": str(path),
        "supplemental_refs_requested": len(supplemental),
        "excluded_ref_addresses_requested": len(excluded),
        "correction_basis": payload.get("basis"),
    }


def marker_spans(plain: bytes, spans: list, texts: list) -> tuple[list, list]:
    """Keep only translations inside trusted 07 1C dialogue blocks."""
    ranges = [(block.text, block.text_end)
              for block in text_blocks.find_blocks(plain)]
    kept = [(span, text) for span, text in zip(spans, texts)
            if any(start <= span.text < end for start, end in ranges)]
    return [span for span, _ in kept], [text for _, text in kept]


def runtime_text_end(stream: bytes, marker: int) -> int:
    """Return the pointer after opcode 07's actual text-skip routine.

    The extractor's 12 10 pair is a reliable translation-span boundary, but it is
    not the interpreter's post-text boundary.  Handler 07 calls the byte scanner at
    0x0884DE70, which starts at marker+1 and consumes one byte for ordinary/control
    values, two bytes for 0x81-0x9F/0xE0-0xFC glyphs, and stops on 00/FD/FE/FF.  The
    main loop then advances once past that sentinel.  References after the sentinel
    are therefore reachable instructions and must not be hidden inside a synthetic
    12 10 block.
    """
    pos = marker + 1
    while pos < len(stream):
        value = stream[pos]
        if value in (0x00, 0xFD, 0xFE, 0xFF):
            return pos + 1
        if 0x81 <= value <= 0x9F or 0xE0 <= value <= 0xFC:
            pos += 2
        else:
            pos += 1
    return len(stream)


def runtime_marker_ends(stream: bytes, blocks: list) -> dict[int, int]:
    return {block.marker: runtime_text_end(stream, block.marker)
            for block in blocks}


def extend_runtime_opaque_flags(flags: bytearray, marker_end: dict[int, int],
                                blocks: list | None = None) -> None:
    """Hide exactly the bytes consumed by handler 07 from the CFG scanner.

    ``ref_manifest.membership`` initially marks through the extractor's 12 10
    delimiter.  For the 277 blocks where the runtime sentinel occurs earlier,
    that would incorrectly hide the executable bytes between the sentinel and
    12 10, so clear each extractor block before applying the runtime range.
    """
    if blocks is not None:
        for block in blocks:
            flags[block.marker:block.end] = b"\x00" * (block.end - block.marker)
    for marker, end in marker_end.items():
        flags[marker:end] = b"\x01" * (end - marker)

# The argument reader at 0x088510B4 is recursive: tags 00-0E are binary
# expressions, while 12-14 and several later tags take one nested expression.
# This is the part the old canonical walk could not represent, and it is why a
# 0C/0D operand appears after more than one byte of typed arguments.
TYPE_ARITY = {
    **{tag: 2 for tag in range(0x00, 0x0F)},
    0x09: 1,
    0x11: 0,
    0x12: 1,
    0x13: 1,
    0x14: 1,
    0x21: 0,
    0x22: 0,
    0x26: 1,
    0x2A: 0,
    0x3B: 1,
    0x3C: 0,
    0x3E: 1,
    0x3F: 1,
    0x41: 0,
    0x4C: 0,
    0x4D: 1,
    0x51: 1,
    0x55: 1,
    0x57: 1,
    0x58: 1,
    0x59: 0,
    0x5A: 1,
    0x5B: 1,
    0x5C: 1,
}
TYPE_PAYLOAD = {0x10: 4, 0x15: 4, 0x16: 1}


def dispatch_opcodes() -> set[int]:
    data = json.loads(OPCODE_TABLE.read_text(encoding="utf-8"))
    return {int(key, 16) for key in data["handlers"]}


def typed_end(stream: bytes, pos: int, depth: int = 0) -> int | None:
    """Return the first byte after one recursive typed expression."""
    if depth > 32 or pos >= len(stream):
        return None
    tag = stream[pos]
    pos += 1
    if tag in TYPE_PAYLOAD:
        end = pos + TYPE_PAYLOAD[tag]
        return end if end <= len(stream) else None
    arity = TYPE_ARITY.get(tag)
    if arity is None:
        return None
    for _ in range(arity):
        pos = typed_end(stream, pos, depth + 1)
        if pos is None:
            return None
    return pos


SECONDARY_PRIMARY = {0x13, 0x14, 0x26, 0x2A}


def full_arg_end(stream: bytes, pos: int) -> int | None:
    """Return the end of opcode 09's two-stage argument."""
    after_primary = typed_end(stream, pos + 1)
    if after_primary is None or after_primary >= len(stream):
        return None
    secondary = stream[after_primary]
    after_secondary = after_primary + 1
    if secondary in SECONDARY_PRIMARY:
        after_secondary = typed_end(stream, after_secondary)
    elif secondary == 0x16:
        after_secondary += 1
    return after_secondary if after_secondary is not None and after_secondary <= len(stream) else None


def collect_typed_pointer_refs(stream: bytes, flags: bytearray,
                               records: dict[int, tuple]
                               ) -> list[tuple[int, int]]:
    """Collect stream pointers hidden inside typed expressions.

    Type ``15`` is not an ordinary four-byte literal.  Its handler at
    ``0x08851304`` reads the value and adds the stream base before returning it,
    so the value is an offset into this very stream and must move when dialogue
    grows.  These fields are nested below opcodes 09/0C/0D/12 and are invisible
    to the top-level jump scan.

    Walk only expressions rooted at CFG-discovered interpreter instructions.  A
    blind byte scan would mistake the payload of opcode 18 (and similar commands)
    for type 15 and would corrupt unrelated data.
    """
    found: dict[int, int] = {}
    visited: set[int] = set()

    def walk(pos: int, depth: int = 0) -> None:
        if pos in visited or pos >= len(stream) or depth > 40 or flags[pos]:
            return
        visited.add(pos)
        tag = stream[pos]
        if tag == 0x15:
            if pos + 5 > len(stream):
                return
            value = int.from_bytes(stream[pos + 1:pos + 5], "little")
            if SCRIPT_START <= value < len(stream):
                operand = pos + 1
                old = found.get(operand)
                if old is not None and old != value:
                    raise ValueError(f"conflicting typed pointer at 0x{operand:x}")
                found[operand] = value
            return
        if tag in TYPE_PAYLOAD:
            return
        arity = TYPE_ARITY.get(tag)
        if arity is None:
            return
        child = pos + 1
        for _ in range(arity):
            walk(child, depth + 1)
            child = typed_end(stream, child, depth + 1)
            if child is None:
                return

    for pos in records:
        opcode = stream[pos]
        roots: list[int] = []
        if opcode in (0x0C, 0x0D, 0x12):
            roots.append(pos + 1)
        elif opcode == 0x09:
            roots.append(pos + 1)
            primary_end = typed_end(stream, pos + 1)
            if (primary_end is not None and primary_end < len(stream)
                    and stream[primary_end] in SECONDARY_PRIMARY):
                roots.append(primary_end + 1)
        for root in roots:
            if root < len(stream):
                walk(root)
    return sorted(found.items())


def parse_cfg_instruction(stream: bytes, flags: bytearray,
                          marker_end: dict[int, int], pos: int) -> tuple[int, str, list] | None:
    """Parse one instruction at a boundary reached by the interpreter CFG."""
    if pos >= len(stream):
        return None
    if pos in marker_end:
        return marker_end[pos], "text", []
    # Opcode 07 always calls the interpreter's byte scanner, even when the
    # payload is a control/status string rather than a translated 07 1C
    # dialogue block.  The extractor deliberately records only 07 1C blocks,
    # so reachable forms such as 07 10 ... 00 must be discovered here as well.
    if stream[pos] == 0x07:
        return runtime_text_end(stream, pos), "text", []
    if flags[pos]:
        return None

    opcode = stream[pos]
    if opcode in (0x00, 0x02):
        return pos + 1, "stop", []
    if opcode == 0x01:
        if pos + 5 > len(stream):
            return None
        target = int.from_bytes(stream[pos + 1:pos + 5], "little")
        return pos + 5, "call", [(pos + 1, target)]
    if opcode in (0x0A, 0x0B):
        if pos + 5 > len(stream):
            return None
        target = int.from_bytes(stream[pos + 1:pos + 5], "little")
        return pos + 5, "jump", [(pos + 1, target)]
    if opcode in (0x0C, 0x0D):
        after_arg = typed_end(stream, pos + 1)
        if after_arg is None or after_arg + 4 > len(stream):
            return None
        if any(flags[pos:after_arg + 4]):
            return None
        target = int.from_bytes(stream[after_arg:after_arg + 4], "little")
        return after_arg + 4, "cond", [(after_arg, target)]
    if opcode == 0x09:
        end = full_arg_end(stream, pos)
        if end is None or any(flags[pos:end]):
            return None
        return end, "other", []
    if opcode in (0x03, 0x04):
        if pos + 1 >= len(stream):
            return None
        end = pos + 12 if stream[pos + 1] == 3 else pos + 2
        return (end, "other", []) if end <= len(stream) and not any(flags[pos:end]) else None
    if opcode == 0x0E:
        # The input/wait handler first reads a signed 16-bit value from the
        # four-byte payload and advances over those four bytes.  For the three
        # sentinel values used by the script format (-41, -50 and -39), it
        # then consumes one more little-endian 16-bit field before returning.
        # Treating every 0E as five bytes makes the next opcode appear at the
        # first byte of that extra field and can hide a real 01/0A/0C/0D edge.
        if pos + 5 > len(stream):
            return None
        signed_value = int.from_bytes(stream[pos + 1:pos + 3], "little", signed=True)
        end = pos + (7 if signed_value in (-41, -50, -39) else 5)
        return (end, "other", []) if end <= len(stream) and not any(flags[pos:end]) else None
    if opcode == 0x0F:
        end = pos + 3
        return (end, "other", []) if end <= len(stream) and not any(flags[pos:end]) else None
    if opcode == 0x10:
        if pos + 1 >= len(stream):
            return None
        end = pos + 10 if stream[pos + 1] == 0xFF else pos + 2
        return (end, "other", []) if end <= len(stream) and not any(flags[pos:end]) else None
    if opcode == 0x12:
        end = typed_end(stream, pos + 1)
        return (end, "other", []) if end is not None and not any(flags[pos:end]) else None

    fixed = {
        0x11: 1, 0x13: 1, 0x14: 1, 0x15: 2, 0x16: 4, 0x17: 1,
        0x18: 7, 0x19: 5, 0x1A: 5, 0x1B: 3, 0x1C: 16,
    }
    if opcode in fixed:
        return pos + fixed[opcode], "other", []
    # The remaining high-byte handlers are the decoder's ordinary one- or two-byte
    # character path.  This is equivalent to opcodes.step for a stateless position.
    end = pos + 2 if (0x81 <= opcode <= 0x9F or 0xE0 <= opcode <= 0xFC) else pos + 1
    return end, "other", []


def collect_runtime_refs(stream: bytes, flags: bytearray
                         ) -> tuple[list[tuple[int, int]], dict, dict[int, tuple]]:
    """Collect references from actual interpreter boundaries, including opcode 01."""
    blocks = text_blocks.find_blocks(stream)
    marker_end = runtime_marker_ends(stream, blocks)
    dispatch = dispatch_opcodes()

    # Header/array targets are already structurally known and make good seeds for
    # otherwise disconnected scene branches.  The first scene entry is the target of
    # header word 3 in this title.
    header, inline = reflow.load_refs(MANIFEST)
    array_refs = load_pointer_array_refs()
    seeds = {0x3764B}
    for _, target in header + inline + array_refs:
        if SCRIPT_START <= target < len(stream):
            seeds.add(target)

    def valid_target(target: int) -> bool:
        return (SCRIPT_START <= target < len(stream)
                and (target in marker_end
                     or (not flags[target] and stream[target] in dispatch)))

    def valid_boundary(target: int) -> bool:
        return target < len(stream) and (target in marker_end or not flags[target])

    work = list(seeds)
    records: dict[int, tuple] = {}
    invalid_positions = []
    invalid_targets = 0
    target_edges = 0
    refs_by_addr: dict[int, int] = {}
    candidates = {f"{opcode:02x}": 0 for opcode in (0x01, 0x0A, 0x0B, 0x0C, 0x0D)}
    selected = {f"{opcode:02x}": 0 for opcode in (0x01, 0x0A, 0x0B, 0x0C, 0x0D)}

    while work:
        pos = work.pop()
        if pos in records or not (SCRIPT_START <= pos < len(stream)):
            continue
        parsed = parse_cfg_instruction(stream, flags, marker_end, pos)
        if parsed is None:
            invalid_positions.append([pos, stream[pos]])
            continue
        end, kind, edges = parsed
        if end <= pos or end > len(stream):
            invalid_positions.append([pos, stream[pos]])
            continue
        records[pos] = parsed
        opcode = stream[pos]
        if opcode in (0x01, 0x0A, 0x0B, 0x0C, 0x0D):
            key = f"{opcode:02x}"
            candidates[key] += 1
            target = edges[0][1]
            target_edges += 1
            if valid_target(target):
                selected[key] += 1
                old = refs_by_addr.get(edges[0][0])
                if old is not None and old != target:
                    raise ValueError(f"conflicting CFG references at 0x{edges[0][0]:x}")
                refs_by_addr[edges[0][0]] = target
                work.append(target)
            else:
                invalid_targets += 1

        # Calls and conditions have a fall-through path.  0A/0B are unconditional.
        if kind == "call" or kind == "cond" or kind not in ("jump", "stop"):
            if valid_boundary(end):
                work.append(end)
        if kind == "text" and valid_boundary(end):
            work.append(end)

    stats = {
        "blocks_used_for_boundary_scan": len(blocks),
        "runtime_text_sentinel_bytes": sum(
            marker_end[block.marker] - block.end for block in blocks),
        "runtime_text_boundary_before_extractor_close": sum(
            marker_end[block.marker] < block.end for block in blocks),
        "cfg_seed_targets": len(seeds),
        "cfg_boundaries": len(records),
        "cfg_invalid_positions": len(invalid_positions),
        "cfg_invalid_position_examples": invalid_positions[:12],
        "cfg_target_edges": target_edges,
        "cfg_invalid_targets": invalid_targets,
        "candidates_by_opcode": candidates,
        "selected_by_opcode": selected,
        "selected_runtime_refs": len(refs_by_addr),
        "emulator_launched": False,
    }
    return sorted(refs_by_addr.items()), stats, records


def load_all_refs(runtime: list[tuple[int, int]], stream: bytes,
                  flags: bytearray, records: dict[int, tuple],
                  supplemental: list[tuple[int, int]] | None = None,
                  excluded: set[int] | None = None,
                  ) -> tuple[list[tuple[int, int]], dict]:
    supplemental = supplemental or []
    excluded = excluded or set()
    header, inline = reflow.load_refs(MANIFEST)
    # The old linear 01 scan can start one byte into a real 0A/0B operand.  Drop such
    # records when a boundary-driven parse proves that the address belongs to another
    # instruction; keep the manifest entries that are not contradicted by the CFG, since
    # they include disconnected scene data and the tail record run.
    starts = sorted(records)
    ends = [records[pos][0] for pos in starts]
    markers = {block.marker for block in text_blocks.find_blocks(stream)}
    dispatch = dispatch_opcodes()
    filtered_inline = []
    dropped_inline = []
    dropped_invalid_target = []
    for addr, value in inline:
        target_is_code = (SCRIPT_START <= value < len(stream)
                          and (value in markers
                               or (not flags[value] and stream[value] in dispatch)))
        if not target_is_code:
            dropped_invalid_target.append([addr, value, stream[value] if 0 <= value < len(stream) else None])
            continue
        index = bisect_right(starts, addr) - 1
        owner = starts[index] if index >= 0 and addr < ends[index] else None
        if owner is not None and not (stream[owner] == 0x01 and addr == owner + 1):
            dropped_inline.append([addr, value, owner, stream[owner]])
            continue
        filtered_inline.append((addr, value))

    refs_before_exclusion = header + filtered_inline
    refs = [(addr, value) for addr, value in refs_before_exclusion if addr not in excluded]
    source = {addr: "manifest_header" for addr, _ in header}
    source.update({addr: "manifest_inline" for addr, _ in filtered_inline})
    for address in excluded:
        source.pop(address, None)

    correction_conflicts = []
    supplemental_added = 0
    for addr, value in supplemental:
        old = next((old_value for old_addr, old_value in refs if old_addr == addr), None)
        if old is not None:
            if old != value:
                correction_conflicts.append([addr, old, value])
            continue
        refs.append((addr, value))
        source[addr] = "cfg17_supplement"
        supplemental_added += 1
    if correction_conflicts:
        raise ValueError(
            "supplemental reference conflicts with structural/manifest reference: "
            f"{correction_conflicts[:8]}"
        )

    # The first 684 tiles are raw 16x16 4bpp glyphs, not pointer-bearing data.
    # A broad manifest/array scan can find byte patterns inside those pixels that
    # look like stream addresses. Reflowing them would leave a valid archive but
    # visibly corrupt the font, so reject every operand overlapping the table.
    protected_font_refs = []

    def overlaps_font_table(addr: int) -> bool:
        return addr < FONT_TABLE_END and addr + 4 > FONT_TABLE_START

    kept_refs = []
    for addr, value in refs:
        if overlaps_font_table(addr):
            protected_font_refs.append([addr, value, source.get(addr, "manifest")])
            source.pop(addr, None)
        else:
            kept_refs.append((addr, value))
    refs = kept_refs

    for addr, value in load_pointer_array_refs():
        if addr in excluded:
            continue
        if overlaps_font_table(addr):
            protected_font_refs.append([addr, value, "pointer_array"])
            continue
        if addr not in source:
            refs.append((addr, value))
            source[addr] = "pointer_array"

    conflicts = []
    manifest_overrides = []
    overlap_rejected = []
    occupied_bytes = set()
    ref_index = {}
    for index, (addr, _) in enumerate(refs):
        ref_index[addr] = index
        occupied_bytes.update(range(addr, addr + 4))
    added = 0
    # The canonical walk deliberately errs on the side of visiting every possible
    # byte boundary.  A byte equal to 0A inside another four-byte operand can therefore
    # look like a second jump three bytes later.  Real reference words cannot overlap;
    # reserve the proven manifest/array words first, then take the earliest non-overlap
    # runtime candidate.  This also prevents a false runtime candidate from overwriting
    # a proven 01 reference.
    for addr, value in sorted(runtime):
        if addr in excluded:
            continue
        if overlaps_font_table(addr):
            protected_font_refs.append([addr, value, "runtime"])
            continue
        if addr in source:
            index = ref_index[addr]
            old = refs[index][1]
            if old != value:
                # The old manifest came from a linear scan.  It can contain the
                # right operand address but an old target that must move when
                # dialogue grows.  A boundary-driven CFG reference at the exact
                # same operand address is stronger evidence and replaces that
                # stale inline value.  Contradictions with structural header or
                # pointer-array references remain fatal.
                if source[addr] == "manifest_inline":
                    refs[index] = (addr, value)
                    manifest_overrides.append([addr, old, value])
                else:
                    conflicts.append([addr, old, value])
            continue
        if any(offset in occupied_bytes for offset in range(addr, addr + 4)):
            overlap_rejected.append([addr, value])
            continue
        refs.append((addr, value))
        source[addr] = "runtime_jump"
        occupied_bytes.update(range(addr, addr + 4))
        added += 1

    return refs, {
        "manifest_header": len(header),
        "manifest_inline": len(inline),
        "manifest_inline_kept": len(filtered_inline),
        "manifest_inline_dropped_inside_cfg_instruction": len(dropped_inline),
        "manifest_inline_dropped_examples": dropped_inline[:12],
        "manifest_inline_dropped_invalid_target": len(dropped_invalid_target),
        "manifest_inline_dropped_invalid_target_examples": dropped_invalid_target[:12],
        "manifest_or_structural_refs_excluded": len(refs_before_exclusion) - len(
            [(addr, value) for addr, value in refs_before_exclusion if addr not in excluded]
        ),
        "supplemental_refs_added": supplemental_added,
        "supplemental_refs_already_present": len(supplemental) - supplemental_added,
        "excluded_ref_addresses": len(excluded),
        "pointer_array_refs_added": sum(1 for kind in source.values() if kind == "pointer_array"),
        "runtime_refs_added": added,
        "runtime_manifest_overrides": len(manifest_overrides),
        "runtime_manifest_override_examples": manifest_overrides[:12],
        "runtime_overlap_rejected": len(overlap_rejected),
        "runtime_overlap_rejected_examples": overlap_rejected[:12],
        "font_table_range": [FONT_TABLE_START, FONT_TABLE_END],
        "font_table_refs_rejected": len(protected_font_refs),
        "font_table_refs_rejected_examples": protected_font_refs[:12],
        "duplicate_or_conflicting_runtime_refs": conflicts,
        "total_refs": len(refs),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True,
                        help="translated stream candidate")
    parser.add_argument("--base", type=Path, default=BASE_STREAM,
                        help="font/text base stream to rebuild")
    parser.add_argument("--tsv", type=Path, default=TSV,
                        help="normalized translation TSV")
    parser.add_argument("--slots", type=Path, default=SLOTS,
                        help="character-to-glyph slot map")
    parser.add_argument("--report", type=Path,
                        default=ROOT / "build" / "runtime_refs_report.json")
    parser.add_argument("--marker-only", action="store_true",
                        help="reflow only strings inside trusted 07 1C dialogue blocks")
    parser.add_argument(
        "--reference-corrections",
        type=Path,
        default=REFERENCE_CORRECTIONS,
        help="CFG17-proven reference additions and exclusions",
    )
    parser.add_argument(
        "--translation-is-final",
        action="store_true",
        help="do not reapply older residual/semantic overrides to the supplied TSV",
    )
    args = parser.parse_args()

    original = ORIGINAL_STREAM.read_bytes()
    base = args.base.read_bytes()
    if len(original) != len(base):
        raise SystemExit(f"stream size mismatch: original={len(original)} base={len(base)}")
    if original[SCRIPT_START:] != base[SCRIPT_START:]:
        raise SystemExit("the Korean-font base differs from the original after script start")

    slots = {char: int(index) for char, index in
             json.loads(args.slots.read_text(encoding="utf-8"))["slots"].items()}
    translated_spans, translated_texts, _ = build_patch.build_spans(
        original,
        args.tsv,
        slots,
        apply_overrides=not args.translation_is_final,
    )
    if args.marker_only:
        translated_spans, translated_texts = marker_spans(
            original, translated_spans, translated_texts)
    blocks = text_blocks.find_blocks(original)
    text_flags = ref_manifest.membership(original, blocks)
    for span in translated_spans:
        text_flags[span.text:span.text_end] = b"\x01" * (span.text_end - span.text)

    # CFG collection must follow the interpreter's text scanner, not only the
    # extractor's 12 10 span delimiter.  The span itself remains unchanged.
    extend_runtime_opaque_flags(text_flags, runtime_marker_ends(original, blocks), blocks)

    runtime, collect_stats, cfg_records = collect_runtime_refs(original, text_flags)
    typed_runtime = collect_typed_pointer_refs(original, text_flags, cfg_records)
    collect_stats["typed_pointer_candidates"] = len(typed_runtime)
    supplemental, excluded, correction_stats = load_reference_corrections(
        args.reference_corrections
    )
    refs, ref_stats = load_all_refs(runtime + typed_runtime, original,
                                    text_flags, cfg_records, supplemental, excluded)
    ref_stats.update(correction_stats)
    ref_stats["typed_pointer_refs_added"] = len(typed_runtime)
    if ref_stats["duplicate_or_conflicting_runtime_refs"]:
        raise SystemExit("runtime reference address conflicts with an existing manifest entry")

    spans, texts, text_stats = build_patch.build_spans(
        base,
        args.tsv,
        slots,
        apply_overrides=not args.translation_is_final,
    )
    if args.marker_only:
        spans, texts = marker_spans(base, spans, texts)
    rebuilt, mapping = reflow.rebuild(base, spans, texts)
    written, skipped = reflow.remap(rebuilt, refs, mapping, len(base))
    if skipped:
        raise SystemExit(f"unexpected references outside stream: {skipped}")

    # Every written word must be exactly the mapped value.  This catches a wrong
    # operand address before an archive or ISO is produced.
    bad = []
    for addr, value in refs:
        actual = int.from_bytes(rebuilt[mapping[addr] : mapping[addr] + 4], "little")
        expected = mapping[value]
        if actual != expected:
            bad.append([addr, value, actual, expected])
            if len(bad) >= 8:
                break
    if bad:
        raise SystemExit(f"reference verification failed: {bad}")

    # Preserve the existing structural checks as diagnostics, but do not claim that
    # those checks prove the runtime interpreter.  The runtime-reference count above
    # is the new part of this candidate.
    output = bytes(rebuilt)
    output_blocks = text_blocks.find_blocks(output)
    report = {
        "schema": "enkaku-sousa-runtime-reference-candidate/v1",
        "source": str(args.base),
        "translation": str(args.tsv),
        "slots": str(args.slots),
        "output": str(args.out),
        "original_size": len(base),
        "output_size": len(output),
        "text": {
            "rows": text_stats["rows"],
            "usable_spans": len(spans),
            "failed": text_stats["failed"],
            "overlap": text_stats["overlap"],
            "old_bytes": sum(span.text_end - span.text for span in spans),
            "new_bytes": sum(map(len, texts)),
        },
        "collection": collect_stats,
        "references": ref_stats | {"written": written},
        "output_structure": {
            "detectable_blocks": len(output_blocks),
            "expected_detectable_blocks": len(text_blocks.find_blocks(original)),
        },
        "emulator_launched": False,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(output)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"-> {args.out}")
    print(f"-> {args.report}")


if __name__ == "__main__":
    main()

"""Read-only deep survey for the translation-quality recovery turn.

Categorises translation_overrides.json by_order by provenance (using the notes field),
inspects every candidate TSV/JSON format, and dumps a machine-readable summary to
build/recovery_survey.json so the recovery plan is built against the real data.

Writes only build/recovery_survey.json. Touches nothing else.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
FE = ROOT / "font_extract"
BUILD = ROOT / "build"


def load_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_tsv(path: Path):
    """Return list of (offset, lines, text) rows, preserving literal \\n in text."""
    if not path.exists():
        return None
    rows = []
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            parts = line.split("\t")
            if len(parts) >= 3:
                rows.append((parts[0], parts[1], "\t".join(parts[2:])))
            else:
                rows.append((parts[0] if parts else "", "", ""))
    return rows


# regex helpers to detect non-Korean / broken content in a KO string
HANGUL = re.compile(r"[가-힣]")
JP_KANA = re.compile(r"[぀-ヿ]")
CJK = re.compile(r"[㐀-鿿]")
REPLACEMENT = re.compile(r"[�]")
COMPAT_JAMO = re.compile(r"[㄰-㆏]")


def classify_notes(entries):
    """Bucket by_order entries into provenance classes using the notes field."""
    buckets = Counter()
    note_samples = {}
    distinct_notes = Counter()
    empty = 0
    per_entry = []  # (order, provenance)
    for order, e in entries:
        note = (e.get("notes") or "").strip()
        ko = (e.get("korean") or "").strip()
        distinct_notes[note] += 1
        if not note:
            prov = "preserve_no_notes"
            empty += 1
        else:
            # heuristics refined after seeing the distribution
            prov = ("BULK" if note in BULK_MARKERS else
                    "MATERIALIZED" if note in MATERIALIZED_MARKERS else
                    "OTHER")
        buckets[prov] += 1
        per_entry.append((order, note, ko))
    return buckets, distinct_notes, empty, per_entry


# filled after first pass inspection; start empty so first run just reports notes
BULK_MARKERS: set[str] = set()
MATERIALIZED_MARKERS: set[str] = set()


def main() -> None:
    out = {}

    # ---- translation_overrides.json ----
    ov = load_json(FE / "translation_overrides.json")
    by_order = ov["by_order"]
    # by_order is a dict keyed by order string; normalise to sorted (int, entry)
    items = sorted(((int(k), v) for k, v in by_order.items()), key=lambda t: t[0])
    out["overrides_meta"] = {
        "version": ov.get("version"),
        "notes": ov.get("notes"),
        "by_order_len": len(by_order),
        "by_japanese_applied_len": len(ov.get("by_japanese_applied") or {}),
        "order_min": items[0][0],
        "order_max": items[-1][0],
        "sample_entry": items[0][1],
    }

    # notes distribution
    distinct_notes = Counter()
    empty_notes = 0
    has_ja = 0
    for _, e in items:
        note = (e.get("notes") or "").strip()
        distinct_notes[note] += 1
        if not note:
            empty_notes += 1
        if (e.get("japanese_reviewed") or "").strip():
            has_ja += 1
    out["notes_distribution"] = {
        "empty_notes": empty_notes,
        "has_japanese_reviewed": has_ja,
        "distinct_note_count": len(distinct_notes),
        "top_notes": distinct_notes.most_common(40),
    }

    # ---- TSV formats ----
    tsv_report = {}
    tsv_names = [
        "translation_ko_clean.tsv",
        "translation_ko_semantic_checked.tsv",
        "translation_ko_quality_checked.tsv",
        "translation_ko_runtime_final.tsv",
        "translation_ko_ellipsis.tsv",
        "translation_ko_pronoun.tsv",
        "translation_ko_retranslated.tsv",
    ]
    ko_rows_cache = {}
    for name in tsv_names:
        rows = read_tsv(BUILD / name)
        if rows is None:
            tsv_report[name] = "MISSING"
            continue
        ko_rows_cache[name] = rows
        offsets = [r[0] for r in rows]
        tsv_report[name] = {
            "rows": len(rows),
            "first3": rows[:3],
            "offset_sorted": offsets == sorted(offsets, key=lambda x: int(x) if x.isdigit() else -1),
            "unique_offsets": len(set(offsets)),
        }
    out["ko_tsv"] = tsv_report

    for src_name in ("script_full_raw.tsv", "script_full_ja_corrected.tsv", "script_full_ja.tsv"):
        rows = read_tsv(FE / src_name)
        if rows is None:
            out.setdefault("source_tsv", {})[src_name] = "MISSING"
            continue
        offsets = [r[0] for r in rows]
        out.setdefault("source_tsv", {})[src_name] = {
            "rows": len(rows),
            "first3": rows[:3],
            "unique_offsets": len(set(offsets)),
        }

    # ---- offset alignment between source and ko TSVs ----
    raw_rows = read_tsv(FE / "script_full_raw.tsv")
    clean_rows = ko_rows_cache.get("translation_ko_clean.tsv")
    if raw_rows and clean_rows:
        raw_off = [r[0] for r in raw_rows]
        clean_off = [r[0] for r in clean_rows]
        out["alignment_raw_vs_clean"] = {
            "raw_rows": len(raw_rows),
            "clean_rows": len(clean_rows),
            "offsets_equal": raw_off == clean_off,
            "raw_only": len(set(raw_off) - set(clean_off)),
            "clean_only": len(set(clean_off) - set(raw_off)),
        }

    # ---- batch files ----
    batches = {}
    for i in range(1, 5):
        b = load_json(BUILD / f"retranslation_batch{i:03d}.json")
        if b is None:
            batches[i] = "MISSING"
            continue
        batches[i] = {
            "type": type(b).__name__,
            "top_keys": list(b.keys()) if isinstance(b, dict) else None,
            "len": len(b) if isinstance(b, (list, dict)) else None,
            "sample": (b[0] if isinstance(b, list) and b else
                       (next(iter(b.items())) if isinstance(b, dict) else None)),
        }
    out["batches"] = batches

    # ---- override files ----
    for name in ("translation_semantic_overrides.json", "translation_quality_overrides.json"):
        d = load_json(FE / name)
        if isinstance(d, dict):
            entry = {"top_keys": list(d.keys())}
            for k, v in d.items():
                if isinstance(v, list) and v:
                    entry[f"{k}_len"] = len(v)
                    entry[f"{k}_sample"] = v[0]
            out.setdefault("override_files", {})[name] = entry

    # ---- report/queue files ----
    for name, path in (
        ("dialogue_defects.json", BUILD / "dialogue_defects.json"),
        ("pronoun_fix_report.json", BUILD / "pronoun_fix_report.json"),
        ("retranslation_queue.json", BUILD / "retranslation_queue.json"),
        ("translation_quality_review.json", BUILD / "translation_quality_review.json"),
    ):
        d = load_json(path)
        if d is None:
            out.setdefault("reports", {})[name] = "MISSING"
            continue
        if isinstance(d, dict):
            info = {"top_keys": list(d.keys())}
            for k, v in d.items():
                if isinstance(v, list):
                    info[f"{k}_len"] = len(v)
                    if v:
                        info[f"{k}_sample"] = v[0]
                elif isinstance(v, dict):
                    info[f"{k}_keys"] = list(v.keys())[:20]
            out.setdefault("reports", {})[name] = info
        elif isinstance(d, list):
            out.setdefault("reports", {})[name] = {"list_len": len(d), "sample": d[0] if d else None}

    (BUILD / "recovery_survey.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("wrote build/recovery_survey.json")
    print("by_order:", out["overrides_meta"]["by_order_len"],
          "empty_notes:", empty_notes, "has_ja:", has_ja)
    print("distinct notes:", len(distinct_notes))
    print("top notes:")
    for note, cnt in distinct_notes.most_common(25):
        disp = (note[:70] + "…") if len(note) > 70 else note
        print(f"  {cnt:5d}  {disp!r}")


if __name__ == "__main__":
    main()

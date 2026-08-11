"""Apply the slot assignments read off the glyph sheet.

Context could narrow these but not settle them, and in three cases it was wrong in a way
context could not have revealed: 画, 箍 and 沢 each own two slots and *neither* slot is the
character the charmap assigned -- 503 draws 保 and 1317 draws 載, 604 draws 互 and 919 draws
籠, 931 draws 勤 and 1144 draws 触.  A context-based fix would have corrected one slot and
left the other quietly wrong.

Every value below was read from the rendered bitmap, so the evidence is the glyph itself.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
SRC = ROOT / "font_extract" / "charmap_quality_corrected.json"
REPORT = ROOT / "build" / "charmap_glyph_readings.json"

# slot -> character, read from build/duplicate_slots.png
READINGS = {
    316: "植", 503: "保", 1317: "載", 604: "互", 919: "籠", 685: "防",
    721: "基", 931: "勤", 1144: "触", 481: "嫌", 378: "必", 626: "再",
    558: "落", 428: "時",
}


def main() -> None:
    charmap = json.loads(SRC.read_text(encoding="utf-8"))
    changed = []
    for slot, char in READINGS.items():
        before = charmap[slot].get("char")
        if before == char:
            continue
        charmap[slot] = {**charmap[slot], "char": char,
                         "source": "glyph_image_reading",
                         "confidence": "high", "previous_char": before}
        changed.append({"slot": slot, "from": before, "to": char,
                        "uses": charmap[slot].get("uses", 0)})

    SRC.write_text(json.dumps(charmap, ensure_ascii=False, indent=1), encoding="utf-8")
    REPORT.write_text(json.dumps({
        "schema": "enkaku_charmap_glyph_readings_v1",
        "method": "slots rendered to build/duplicate_slots.png and identified by eye",
        "changed": changed,
        "total_uses_affected": sum(c["uses"] for c in changed),
        "emulator_launched": False,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(changed)} slots reassigned from the glyph images")
    for c in sorted(changed, key=lambda x: -x["uses"]):
        print(f"   slot {c['slot']:5d}  {c['from']} -> {c['to']}   ({c['uses']} uses)")
    print(f"total uses affected: {sum(c['uses'] for c in changed)}")
    print(f"-> {SRC}\n-> {REPORT}")


if __name__ == "__main__":
    main()

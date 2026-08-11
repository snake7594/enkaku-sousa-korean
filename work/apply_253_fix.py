"""Switch every tool from the *256 glyph-index formula to the confirmed *253 one.

Codes with lead 0x88 gave the same answer under either formula, which is why the error
survived so long — the whole first block matched.  It only showed up once a patch
targeted a glyph above 255.
"""

from __future__ import annotations

from pathlib import Path

OLD_NEW = {
    "check_order.py": [
        ("out.append((b - KANJI_LO) * 256 + span[i + 1])",
         "out.append(kanji_index(b, span[i + 1]))"),
        ("from decode_script import (KANJI_HI, KANJI_LO, LEAD_HI, LEAD_LO, STREAM, text_spans)",
         "from decode_script import (KANJI_HI, KANJI_LO, LEAD_HI, LEAD_LO, STREAM,\n"
         "                           kanji_index, text_spans)"),
    ],
    "decode_script.py": [
        ("index = (b - KANJI_LO) * 256 + trail", "index = kanji_index(b, trail)"),
    ],
    "extract_all_text.py": [
        ('out.append(f"[{(b - KANJI_LO) * 256 + trail}]")',
         'out.append(f"[{kanji_index(b, trail)}]")'),
        ("from decode_script import (HALFWIDTH, HIRA, HIRA_BASE, KANJI_HI, KANJI_LO,\n"
         "                           LEAD_HI, LEAD_LO, STREAM)",
         "from decode_script import (HALFWIDTH, HIRA, HIRA_BASE, KANJI_HI, KANJI_LO,\n"
         "                           LEAD_HI, LEAD_LO, STREAM, kanji_index)"),
    ],
    "extract_ruby.py": [
        ('tokens.append(("kanji", (b - KANJI_LO) * 256 + span[i + 1]))',
         'tokens.append(("kanji", kanji_index(b, span[i + 1])))'),
    ],
    "findline.py": [
        ("glyphs.append((raw[i] - 0x88) * 256 + raw[i + 1])",
         "glyphs.append(kanji_index(raw[i], raw[i + 1]))"),
    ],
    "improve_charmap.py": [
        ('tokens.append(("kanji", (b - KANJI_LO) * 256 + span[i + 1]))',
         'tokens.append(("kanji", kanji_index(b, span[i + 1])))'),
    ],
    "match_screenshot.py": [
        ("kanji.append((data[k] - 0x88) * 256 + data[k + 1])",
         "kanji.append(kanji_index(data[k], data[k + 1]))"),
    ],
    "ruby.py": [
        ('tokens.append(("kanji", (b - KANJI_LO) * 256 + span[i + 1]))',
         'tokens.append(("kanji", kanji_index(b, span[i + 1])))'),
        ("from decode_script import (HALFWIDTH, HIRA, HIRA_BASE, KANJI_HI, KANJI_LO,\n"
         "                           LEAD_HI, LEAD_LO, STREAM, text_spans)",
         "from decode_script import (HALFWIDTH, HIRA, HIRA_BASE, KANJI_HI, KANJI_LO,\n"
         "                           LEAD_HI, LEAD_LO, STREAM, kanji_index, text_spans)"),
    ],
}

IMPORT_LINE = "from decode_script import kanji_index\n"


def main() -> None:
    work = Path(__file__).parent
    for name, pairs in OLD_NEW.items():
        path = work / name
        if not path.exists():
            print(f"missing {name}")
            continue
        text = path.read_text(encoding="utf-8")
        before = text
        for old, new in pairs:
            text = text.replace(old, new)
        if "kanji_index(" in text and "kanji_index" not in text.split("\n\n")[0]:
            if "from decode_script import" not in text:
                lines = text.split("\n")
                for i, line in enumerate(lines):
                    if line.startswith("import ") or line.startswith("from "):
                        lines.insert(i, IMPORT_LINE.rstrip())
                        break
                text = "\n".join(lines)
        path.write_text(text, encoding="utf-8")
        print(("changed  " if text != before else "unchanged") + f" {name}")


if __name__ == "__main__":
    main()

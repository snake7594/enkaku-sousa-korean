"""Re-wrap Korean script lines so none runs past the right edge of the text box.

Issue #4 shows two lines cut off.  Both were measured off the screenshots:

    text starts at PSP x=203 and the screen is 480 wide  -> 277px, and Hangul advances 16px,
    so the box holds 16 full-width glyphs -- 33 half-widths.  The two clipped lines are 34
    and 35.

    lines are 25px apart starting at PSP y=44, and the command bar starts at y=248,
    so the box holds eight lines.  The screenshots use four and six.

The row's own Japanese looked like it should give the width, since the Japanese fits by
construction -- but it does not.  Japanese rows run to 66 half-widths by this count with no
break in the distribution and no clustering by script region, which means the Japanese face is
proportional: its kana advance far less than 16px.  Counting characters therefore says nothing
about how much room the Korean needs, and the measured 33 stands for every row.

Two repairs come out of that:

* lines over 33 get their tail pushed down, cascading until a line has room;
* rows over eight lines get re-flowed, because they do not fit at all.

The first leaves every break the translator did not have to move.  The second cannot -- a row
that overflows the box has to be re-packed -- so it is only done where the row is too tall.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

import translation_text

ROOT = Path(r"D:\psp\원격수사")
TAG = re.compile(r"^【[^】]*】$")
RUBY = re.compile(r"《[^》]*》")
RUN = re.compile(r"(.)\1+")
HALF = re.compile(r"[\x20-\x7e\uff61-\uff9f]")


def width(text: str) -> int:
    """Half-widths on screen.  Ruby in 《》 is drawn above the line and takes no room."""
    return sum(1 if HALF.match(c) else 2 for c in RUBY.sub("", text))


def shrink(line, limit):
    """Trim a run of one repeated character until the line fits.

    Two lines have no space to break at because they are screams -- 꺄아아아…!! and
    그아아아…악!!! -- and a scream is exactly the thing that can lose a letter without losing
    anything.  Runs shorter than five are left alone so this cannot touch ordinary text.
    """
    while width(line) > limit:
        runs = [m for m in RUN.finditer(line) if len(m.group(0)) >= 5]
        if not runs:
            return line
        longest = max(runs, key=lambda m: len(m.group(0)))
        line = line[:longest.start()] + longest.group(0)[:-1] + line[longest.end():]
    return line


def fits(lines, limit, max_lines):
    return len(lines) <= max_lines and all(width(l) <= limit for l in lines)


def split_head(lines):
    """Peel off a speaker label, which the engine frames on its own line."""
    if lines and TAG.match(lines[0]):
        return lines[:1], lines[1:]
    return [], list(lines)


def cascade(lines, limit):
    """Move each over-long line's tail onto the next, letting the overflow run down the row.

    Pushing once and giving up was the first attempt and it refused most rows: the line below
    is usually near full itself, so a single shove only moves the problem.  Going top to bottom
    lets the displaced words keep travelling until a line has room for them.

    Returns None when the row cannot be made to fit -- the overflow reaches the last line, or a
    single word is wider than the box -- and then nothing is changed at all.
    """
    lines = list(lines)
    for i, line in enumerate(lines):
        if width(line) <= limit:
            continue
        if i + 1 >= len(lines):
            return None
        words = line.split()
        moved = []
        while words and width(" ".join(words)) > limit:
            moved.insert(0, words.pop())
        if not words:
            return None                   # one unbreakable word, longer than the line
        following = lines[i + 1]
        lines[i] = " ".join(words)
        lines[i + 1] = " ".join(moved + ([following] if following.strip() else []))
    return lines


def relieve(lines, limit, max_lines):
    """Fix over-long lines without disturbing the breaks that already fit."""
    room = max(0, max_lines - len(lines))
    packed = cascade(list(lines) + [""] * room, limit)
    if packed is None:
        return None
    while len(packed) > len(lines) and not packed[-1]:
        packed.pop()                      # give back the room that went unused
    return packed


def reflow(lines, limit, max_lines):
    """Re-pack a row from scratch, ignoring the breaks it has now.

    Only for rows the gentle pass cannot fix.  Blank lines go with it -- a row that does not
    fit cannot afford them -- but the speaker label keeps its own line.
    """
    head, body = split_head(lines)
    out, current = [], ""
    for word in " ".join(l for l in body if l.strip()).split():
        candidate = f"{current} {word}".strip()
        if current and width(candidate) > limit:
            out.append(current)
            current = word
        else:
            current = candidate
    if current:
        out.append(current)
    packed = head + out
    return packed if fits(packed, limit, max_lines) else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ko", type=Path, default=ROOT / "build" / "translation_ko_v6.tsv")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "translation_ko_v7.tsv")
    parser.add_argument("--limit", type=int, default=33,
                        help="half-widths the text box holds")
    parser.add_argument("--max-lines", type=int, default=8,
                        help="lines the text box holds")
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "rewrap.json")
    args = parser.parse_args()

    header, ko_rows = translation_text.parse_loose_tsv(args.ko)
    rows = [list(r) for r in ko_rows if len(r) >= 3]

    changed, refused = [], []
    for row in rows:
        text = row[2]
        lines = text.split("\\n")
        if not (any(width(l) > args.limit for l in lines) or len(lines) > args.max_lines):
            continue
        # ［…］ rows are entries in a choice list, drawn one per row rather than in the text
        # box.  Breaking one across two lines would push the rest of the list down.
        if text.lstrip().startswith(("［", "[")):
            continue

        lines = [shrink(l, args.limit) if width(l) > args.limit else l for l in lines]
        packed = relieve(lines, args.limit, args.max_lines)
        if packed is None or not fits(packed, args.limit, args.max_lines):
            packed = reflow(lines, args.limit, args.max_lines)
        if packed is None:
            refused.append({"offset": row[0], "ko": text[:80],
                            "widest": max(width(l) for l in lines), "lines": len(lines)})
            continue
        rebuilt = "\\n".join(packed)
        if rebuilt != text:
            changed.append({"offset": row[0], "before": text[:90], "after": rebuilt[:90]})
            row[2] = rebuilt

    args.out.write_text(header + "\n" + "\n".join("\t".join(r) for r in rows) + "\n",
                        encoding="utf-8")
    args.report.write_text(json.dumps(
        {"schema": "enkaku_rewrap_v3", "limit": args.limit, "max_lines": args.max_lines,
         "rewrapped": len(changed), "left_alone": len(refused),
         "changed": changed, "refused": refused}, ensure_ascii=False, indent=1),
        encoding="utf-8")

    tally = collections.Counter(len(r[2].split("\\n")) for r in rows)
    print(f"{len(changed)} rows re-wrapped, {len(refused)} left alone")
    print("lines per row: " + "  ".join(f"{n}->{tally[n]}" for n in sorted(tally)))
    for c in changed[:3]:
        print(f"   {c['offset']}\n     - {c['before']}\n     + {c['after']}")
    print(f"-> {args.out}\n-> {args.report}")


if __name__ == "__main__":
    main()

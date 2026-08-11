"""Find the slot boundaries in the 256x64 HUD atlas by luminance.

The first attempt at this used alpha and reported one slot spanning the whole 256 pixels,
which is why the atlas was left alone.  Alpha was the wrong signal -- the same mistake that
made the settings panel look empty.  Measuring against the local luminance floor separated
the labels there, so it is worth trying here before concluding the slots can only come from
the executable's UV table.

Nothing is written; this reports the runs so the next step can be decided on evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

import texpack

ROOT = Path(r"D:\psp\원격수사")


def runs_of(mask: np.ndarray, gap: int) -> list[tuple[int, int]]:
    out, start, blank = [], None, 0
    for i, on in enumerate(mask):
        if on:
            if start is None:
                start = i
            blank = 0
        elif start is not None:
            blank += 1
            if blank >= gap:
                out.append((start, i - blank))
                start = None
    if start is not None:
        out.append((start, len(mask) - 1))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--gap", type=int, default=2)
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "atlas_slots.json")
    args = parser.parse_args()

    data = args.stream.read_bytes()
    result = {}
    for tex in texpack.load_textures(data):
        if (tex.width, tex.height) != (256, 64):
            continue
        px = np.asarray(texpack.decode(tex).convert("RGBA")).astype(np.int32)
        luma = px[:, :, :3].mean(axis=2)
        opaque = px[:, :, 3] > 40
        floor = float(np.median(luma[opaque])) if opaque.any() else 0.0
        ink = (np.abs(luma - floor) > 20) & opaque

        # rows of an atlas are packed tightly; a two-row gap merges all four into one band
        rows = runs_of(ink.sum(axis=1) >= 2, 1)
        print(f"\ntex{tex.index:04d}  {len(rows)} text rows")
        entry = []
        for top, bottom in rows:
            cols = ink[top:bottom + 1].sum(axis=0) >= 1
            spans = [s for s in runs_of(cols, args.gap) if s[1] - s[0] >= 5]
            print(f"   y {top:2d}-{bottom:2d}: {len(spans)} slots  "
                  f"{[(a, b - a + 1) for a, b in spans][:10]}")
            entry.append({"top": top, "bottom": bottom,
                          "slots": [[a, b] for a, b in spans]})
        result[str(tex.index)] = entry

        image = texpack.decode(tex).resize((tex.width * 3, tex.height * 3), Image.NEAREST)
        image.save(ROOT / "build" / f"atlas_{tex.index}.png")

    args.out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

"""Measure where the original Japanese labels sit, in the panel and in the overlays.

The report asks for the grey background text to line up with the yellow selected text.  They
drifted apart because the two are produced differently: the panel text was drawn at
coordinates I chose, and the 128x32 overlays were centred in their box while the Japanese
originals are left-aligned. Guessing a correction from a screenshot would fix one screen and
break the next, so both are measured from the untouched textures instead.

For each, the ink bounding box is found by luminance against the local background -- the
panel is fully opaque, so alpha says nothing about where the glyphs are.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import texpack

ROOT = Path(r"D:\psp\원격수사")
ITEM_INDICES = [282, 283, 284, 285, 286, 288, 289, 290]


def ink_box(px: np.ndarray, thresh: float = 14.0):
    """Bounding box of pixels that differ from the field, or None."""
    luma = px[:, :, :3].mean(axis=2)
    floor = float(np.median(luma))
    mask = np.abs(luma - floor) > thresh
    if px.shape[2] == 4 and px[:, :, 3].min() < 250:
        mask &= px[:, :, 3] > 40
    if not mask.any():
        return None
    ys, xs = np.nonzero(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "label_metrics.json")
    args = parser.parse_args()

    data = args.stream.read_bytes()
    textures = {t.index: t for t in texpack.load_textures(data)}

    # panel: scan each candidate row band for ink in the left column
    panel = np.asarray(texpack.decode(textures[278]).convert("RGBA")).astype(np.int32)
    luma = panel[:, :, :3].mean(axis=2)
    strip = luma[:, 20:280]
    floor = float(np.median(strip))
    rows_on = (np.abs(strip - floor) > 14).sum(axis=1) >= 2
    runs, start = [], None
    for y, on in enumerate(rows_on):
        if on and start is None:
            start = y
        elif not on and start is not None:
            if y - start >= 4:
                runs.append((start, y - 1))
            start = None
    print(f"panel tex0278: {len(runs)} ink bands in the left column")
    for a, b in runs:
        band = panel[a:b + 1, 20:280]
        box = ink_box(band)
        if box:
            print(f"   y {a:3d}-{b:3d}  x {20 + box[0]:3d}-{20 + box[2]:3d}  h {b - a + 1}")

    print("\noverlay textures (128x32), ink box inside each:")
    overlays = {}
    for i in ITEM_INDICES:
        tex = textures.get(i)
        if tex is None:
            continue
        px = np.asarray(texpack.decode(tex).convert("RGBA")).astype(np.int32)
        box = ink_box(px)
        overlays[i] = box
        print(f"   tex{i:04d}  {box}")

    args.out.write_text(json.dumps(
        {"panel_bands": runs, "overlay_boxes": {str(k): v for k, v in overlays.items()}},
        indent=1), encoding="utf-8")
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

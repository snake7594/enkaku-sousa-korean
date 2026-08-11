"""Pick the font / size / offset that best reproduces the game's glyph bitmaps.

Calibration uses the glyphs already identified by eye from the font sheet.
"""

from __future__ import annotations

import argparse
from itertools import product

import numpy as np

import charmap
from charmap import RenderConfig

# glyph index -> character, read off the extracted font sheet
KNOWN = {
    0: "新", 1: "情", 2: "報", 3: "入", 4: "手", 5: "東", 6: "京",
    7: "年", 8: "発", 9: "売", 10: "千", 11: "定", 107: "光", 108: "志",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()

    glyphs = charmap.game_glyphs()
    indices = sorted(KNOWN)
    targets = glyphs[indices]
    chars = [KNOWN[i] for i in indices]

    results = []
    sizes = [52, 56, 60, 64, 68, 72]
    offsets = [-1.5, -1.0, -0.5, 0.0, 0.5, 1.0]
    for font_file, face in charmap.CANDIDATE_FONTS:
        for px, dx, dy in product(sizes, offsets, offsets):
            config = RenderConfig(font_file, face, px, dx, dy)
            try:
                rendered = charmap.render_set(chars, config)
            except Exception:  # noqa: BLE001 - some faces refuse some sizes
                continue
            scores = charmap.zncc_matrix(targets, rendered)
            mean = float(np.mean(np.diag(scores)))
            results.append((mean, config))

    results.sort(key=lambda r: -r[0])
    print(f"{len(results)} configurations tried; best:")
    for mean, config in results[: args.top]:
        print(f"   zncc={mean:.4f}  {config.label()}")


if __name__ == "__main__":
    main()

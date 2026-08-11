"""Group PPSSPP's dumped textures by dimensions and flag glyph/text-atlas candidates."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args()

    dims = Counter()
    by_dim: dict[tuple[int, int], list[Path]] = defaultdict(list)
    for path in args.folder.rglob("*.png"):
        try:
            with Image.open(path) as im:
                size = im.size
        except Exception:  # noqa: BLE001 - skip unreadable dumps
            continue
        dims[size] += 1
        by_dim[size].append(path)

    print(f"{sum(dims.values())} textures, {len(dims)} distinct sizes")
    for size, count in dims.most_common(args.top):
        print(f"   {size[0]:4d}x{size[1]:<4d}  {count}")

    print("\nlargest textures:")
    for size in sorted(dims, key=lambda s: -s[0] * s[1])[:12]:
        sample = by_dim[size][0]
        print(f"   {size[0]:4d}x{size[1]:<4d} count={dims[size]:<4d} e.g. {sample.name}")

    # a glyph atlas is mostly transparent/monochrome with a lot of small strokes
    print("\nmonochrome-ish candidates (>=128px, single hue, partly transparent):")
    hits = []
    for size, paths in by_dim.items():
        if size[0] * size[1] < 128 * 32:
            continue
        for path in paths[:4]:
            try:
                arr = np.asarray(Image.open(path).convert("RGBA"))
            except Exception:  # noqa: BLE001
                continue
            alpha = arr[..., 3]
            rgb = arr[..., :3].astype(np.int16)
            spread = (rgb.max(axis=2) - rgb.min(axis=2)).mean()
            trans = float(np.mean(alpha < 16))
            if spread < 12 and 0.15 < trans < 0.97:
                hits.append((trans, spread, size, path))
    hits.sort(key=lambda h: -h[2][0] * h[2][1])
    for trans, spread, size, path in hits[:30]:
        print(f"   {size[0]:4d}x{size[1]:<4d} transparent={trans:.2f} hue_spread={spread:.1f}  {path.name}")


if __name__ == "__main__":
    main()

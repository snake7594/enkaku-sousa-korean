"""Look at tex0278 closely enough to place the labels, since detection found nothing.

Two thresholds failed on this texture -- alpha, because the panel is opaque, and a fixed
luminance step, because the labels turn out to sit on a field whose brightness is close to
theirs.  So this reports what is actually in the pixels: the luminance profile row by row,
which shows where the label lines are even when a single cutoff cannot separate them.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

import texpack

ROOT = Path(r"D:\psp\원격수사")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=int, default=278)
    parser.add_argument("--stream", type=Path, default=ROOT / "build" / "stream0.bin")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "tex278_probe.png")
    args = parser.parse_args()

    data = args.stream.read_bytes()
    tex = next(t for t in texpack.load_textures(data) if t.index == args.index)
    image = texpack.decode(tex).convert("RGBA")
    px = np.asarray(image).astype(np.int32)
    luma = px[:, :, :3].mean(axis=2)
    print(f"tex{tex.index:04d} {tex.width}x{tex.height}")
    print(f"   alpha: min {px[:, :, 3].min()} max {px[:, :, 3].max()}")
    print(f"   luma:  min {luma.min():.0f} max {luma.max():.0f} "
          f"median {np.median(luma):.0f}")

    left = luma[:, 20:270]
    print("\n   row profile of the item column (y: max-median):")
    for y in range(70, tex.height, 4):
        band = left[y:y + 4]
        print(f"      {y:3d}  max {band.max():5.0f}  med {np.median(band):5.0f}  "
              f"spread {band.max() - np.median(band):5.0f}")

    image.resize((tex.width * 2, tex.height * 2), Image.NEAREST).save(args.out)
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()

"""Render every texture of a stream and score each one for "looks like a glyph atlas"."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

import texpack


def score(tex: texpack.Texture) -> tuple[float, float, int]:
    """Return (grayscale ratio, transparent ratio, distinct colours) of the palette."""
    colours = np.frombuffer(tex.palette, dtype=np.uint8)
    colours = colours[: (len(colours) // 4) * 4].reshape(-1, 4)
    rgb = colours[:, :3].astype(np.int16)
    gray = float(np.mean((rgb.max(axis=1) - rgb.min(axis=1)) <= 8))
    alpha0 = float(np.mean(colours[:, 3] == 0))
    unique = len({tuple(c) for c in colours})
    return gray, alpha0, unique


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stream", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--only", type=int, nargs="*", default=None)
    args = parser.parse_args()

    textures = texpack.load_stream(args.stream)
    print(f"{len(textures)} textures")
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)

    for tex in textures:
        if args.only and tex.index not in args.only:
            continue
        gray, alpha0, unique = score(tex)
        pixels = tex.width * tex.height
        flag = ""
        if gray > 0.85 and pixels >= 0x4000:
            flag = "  <== glyph-atlas candidate"
        print(
            f"{tex.index:4d} rec{tex.record_index:4d} {tex.width:4d}x{tex.height:<4d} {tex.psm_name:<5s}"
            f" img=0x{len(tex.image):<6x} pal=0x{len(tex.palette):<4x}"
            f" gray={gray:.2f} a0={alpha0:.2f} uniq={unique:<3d}{flag}"
        )
        if args.out:
            image = texpack.decode(tex)
            if image is not None:
                image.save(args.out / f"t{tex.index:04d}_{tex.width}x{tex.height}_{tex.psm_name}.png")


if __name__ == "__main__":
    main()

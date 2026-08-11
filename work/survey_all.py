"""Survey every dumped stream: how many textures, what sizes/formats, and which
look like text (grayscale palette + large + high ink periodicity)."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import numpy as np

import texpack


def palette_stats(palette: bytes) -> tuple[float, float]:
    colours = np.frombuffer(palette, dtype=np.uint8)
    colours = colours[: (len(colours) // 4) * 4].reshape(-1, 4)
    rgb = colours[:, :3].astype(np.int16)
    gray = float(np.mean((rgb.max(axis=1) - rgb.min(axis=1)) <= 8))
    alpha0 = float(np.mean(colours[:, 3] == 0))
    return gray, alpha0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dumps", type=Path, nargs="+")
    parser.add_argument("--render", type=Path, default=None)
    parser.add_argument("--sample", type=int, default=0, help="render only the first N textures per archive")
    args = parser.parse_args()

    for dump in args.dumps:
        streams = sorted(dump.glob("*.bin"))
        sizes = Counter()
        formats = Counter()
        total = 0
        rendered = 0
        print(f"== {dump.name}: {len(streams)} streams")
        for stream in streams:
            try:
                textures = texpack.load_textures(stream.read_bytes())
            except Exception as exc:  # noqa: BLE001 - survey tool, keep going
                print(f"   !! {stream.name}: {exc}")
                continue
            for tex in textures:
                total += 1
                sizes[(tex.width, tex.height)] += 1
                formats[tex.psm_name] += 1
                if args.render and (not args.sample or rendered < args.sample):
                    gray, _ = palette_stats(tex.palette)
                    image = texpack.decode(tex)
                    if image is None:
                        continue
                    out = args.render / dump.name
                    out.mkdir(parents=True, exist_ok=True)
                    name = f"{stream.stem}_t{tex.index:03d}_{tex.width}x{tex.height}_{tex.psm_name}_g{gray:.2f}.png"
                    image.save(out / name)
                    rendered += 1
        print(f"   textures: {total}")
        print(f"   formats : {formats.most_common()}")
        print(f"   sizes   : {sizes.most_common(10)}")


if __name__ == "__main__":
    main()

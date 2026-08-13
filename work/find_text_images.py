"""Pick out the text images among the 700-odd pictures in 0001-0004.

Most of them are scene backgrounds, which are opaque edge to edge.  An overlay -- a banner, a
caption, the title screen's prompt -- is mostly transparent with the ink in one band.  Sorting
by how much of the picture is actually drawn separates the two without having to look at
hundreds of backgrounds.

The tile count says the same thing from the other side: a background stores every tile, an
overlay stores only the tiles its text touches.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import decode_container
import read_blocks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="*", default=["0001", "0002", "0003", "0004"])
    parser.add_argument("--coverage", type=float, default=0.55,
                        help="keep images with at most this fraction of their tiles stored")
    parser.add_argument("--out", type=Path, default=Path(r"D:\psp\원격수사\build\overlays"))
    parser.add_argument("--report", type=Path,
                        default=Path(r"D:\psp\원격수사\build\overlays.json"))
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    kept, seen = [], 0
    for name in args.names:
        blob = (read_blocks.ROOT / name).read_bytes()
        for at, payload in read_blocks.blocks(blob):
            plain, _ = read_blocks.open_stream(payload)
            if plain is None:
                continue
            for n, image, header in decode_container.decode_stream(plain):
                seen += 1
                share = header["tiles"] / max(1, header["tiles_full"])
                alpha = np.asarray(image)[:, :, 3]
                ink = float((alpha > 16).mean())
                if share > args.coverage and ink > args.coverage:
                    continue
                label = f"{name}_{at:07x}_{n}"
                image.save(args.out / f"{label}_{image.width}x{image.height}.png")
                kept.append({"file": name, "block": at, "record": n,
                             "size": [image.width, image.height],
                             "tiles": header["tiles"], "of": header["tiles_full"],
                             "ink": round(ink, 3)})

    kept.sort(key=lambda k: k["ink"])
    args.report.write_text(json.dumps({"schema": "enkaku_overlays_v1", "images": kept},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{seen} images, {len(kept)} look like overlays")
    for k in kept[:25]:
        print(f"   {k['file']}@{k['block']:#09x} rec{k['record']}  "
              f"{k['size'][0]}x{k['size'][1]}  tiles {k['tiles']}/{k['of']}  ink {k['ink']}")
    print(f"-> {args.out}\n-> {args.report}")


if __name__ == "__main__":
    main()

"""Pull out the text-bearing pictures from 0001-0004 so they can be translated.

With the container decoded, 0001 turns out to hold the whole tutorial -- `調査依頼について`,
`辞典について`, `尋問について` and the rest, several pages each, set as full 512x256 pictures --
plus the scene banners (`尋問開始`, `前日の調査報告`, `報告終了`), the location labels, and the
startup notices.  None of it has ever been touched by the patch, because none of it was
reachable until the archive opened.

Backgrounds and character art are skipped: an image is kept when it stores well under its full
complement of tiles, which is what an overlay of type on a dark ground looks like.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import decode_container
import read_blocks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="*", default=["0001", "0003", "0004"])
    parser.add_argument("--out", type=Path, default=Path(r"D:\psp\원격수사\build\container_text"))
    parser.add_argument("--report", type=Path,
                        default=Path(r"D:\psp\원격수사\build\container_text.json"))
    parser.add_argument("--max-share", type=float, default=0.85,
                        help="keep images storing at most this share of their tiles")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    kept = []
    for name in args.names:
        blob = (read_blocks.ROOT / name).read_bytes()
        for at, payload in read_blocks.blocks(blob):
            plain, _ = read_blocks.open_stream(payload)
            if plain is None:
                continue
            for n, image, header in decode_container.decode_stream(plain):
                share = header["tiles"] / max(1, header["tiles_full"])
                small = image.width < 512 or image.height < 256
                # A full-screen picture that stores every tile is scene art.  Anything smaller
                # is a UI element, and those are worth looking at whether they are sparse or not
                # -- the 尋問開始 banners fill all sixteen of their tiles.
                if not small and share > args.max_share:
                    continue
                label = f"{name}_{at:07x}_{n}"
                image.save(args.out / f"{label}.png")
                kept.append({"id": label, "file": name, "block": at, "record": n,
                             "size": [image.width, image.height],
                             "tiles": header["tiles"], "of": header["tiles_full"]})

    args.report.write_text(json.dumps({"schema": "enkaku_container_text_v1", "images": kept},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
    by_size: dict[tuple[int, int], int] = {}
    for k in kept:
        key = tuple(k["size"])
        by_size[key] = by_size.get(key, 0) + 1
    print(f"{len(kept)} candidate text images")
    for (w, h), n in sorted(by_size.items(), key=lambda kv: -kv[1]):
        print(f"   {n:>4d}  {w}x{h}")
    print(f"-> {args.out}\n-> {args.report}")


if __name__ == "__main__":
    main()

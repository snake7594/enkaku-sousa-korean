"""Find the glyph tile the game actually uploaded, and compare it with what we wrote.

PPSSPP dumps every texture the game binds, so the 32x16 tile holding the patched
speaker name is in there.  Comparing it against the bitmap we put in the archive shows
whether the pixels survived the trip — and if they did not, the shape of the damage
tells us what transform the engine applies that we are not reproducing.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

import font as fontlib
import lzss

TEXTURES = Path(r"D:\psp\ppsspp_win\memstick\PSP\TEXTURES\UCJS10088")
BUILD_STREAM = Path(r"D:\psp\원격수사\build\stream1_hangul3.bin")
FONT_OFFSET = 0x80
FONT_TILES = 684


def tile_from_stream(path: Path, first_glyph: int) -> np.ndarray:
    """(16, 32) coverage of the tile holding first_glyph and its partner."""
    plain = path.read_bytes()
    glyphs = fontlib.tiles_to_glyphs(plain, FONT_OFFSET, FONT_TILES)
    pair = first_glyph - (first_glyph % 2)
    return np.concatenate([glyphs[pair], glyphs[pair + 1]], axis=1)


def normalised(a: np.ndarray) -> np.ndarray:
    a = a.astype(np.float32)
    a -= a.mean()
    n = np.linalg.norm(a)
    return a / n if n else a


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--glyph", type=int, default=107)
    parser.add_argument("--since", default="2026-08-07 17:00")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--top", type=int, default=4)
    args = parser.parse_args()

    import datetime
    since = datetime.datetime.fromisoformat(args.since).timestamp()

    want = tile_from_stream(BUILD_STREAM, args.glyph)
    ref = normalised(want)

    scored = []
    for path in TEXTURES.rglob("*.png"):
        if path.stat().st_mtime < since:
            continue
        try:
            image = Image.open(path)
            if image.size != (32, 16):
                continue
            arr = np.asarray(image.convert("RGBA"))
        except Exception:  # noqa: BLE001
            continue
        alpha = arr[..., 3].astype(np.float32)
        scored.append((float((normalised(alpha) * ref).sum()), path, alpha))

    scored.sort(key=lambda s: -s[0])
    print(f"{len(scored)} dumped 32x16 tiles considered")
    for score, path, _ in scored[: args.top]:
        print(f"   {score:+.3f}  {path.name}")

    if not scored:
        return
    rows = [want.astype(np.float32) / 15.0 * 255.0]
    labels = ["what we wrote"]
    for score, path, alpha in scored[: args.top]:
        rows.append(alpha)
        labels.append(f"{path.name} ({score:+.2f})")

    sheet = np.zeros((len(rows) * 19, 32), dtype=np.uint8)
    for i, row in enumerate(rows):
        sheet[i * 19 : i * 19 + 16, :] = np.clip(row, 0, 255).astype(np.uint8)
    Image.fromarray(sheet, "L").resize((32 * 10, sheet.shape[0] * 10), Image.NEAREST).save(args.out)
    for i, label in enumerate(labels):
        print(f"   row {i}: {label}")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

"""Work out what the engine does to glyph pixels between the archive and the texture.

PPSSPP's dump is ground truth for what reached VRAM.  Comparing it against the bytes we
wrote, under a range of candidate transforms, identifies the one the engine applies —
the winning transform is the one we have to reproduce when authoring glyphs.

The left half of the tile is untouched original game data, so it doubles as a control:
whatever transform explains the patched half must leave the control matching too.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

import font as fontlib

BUILD_STREAM = Path(r"D:\psp\원격수사\build\stream1_hangul3.bin")
ORIG_STREAM = Path(r"D:\psp\원격수사\font_extract\script_stream.bin")
FONT_OFFSET = 0x80
FONT_TILES = 684


def tile_of(path: Path, glyph: int) -> np.ndarray:
    glyphs = fontlib.tiles_to_glyphs(path.read_bytes(), FONT_OFFSET, FONT_TILES)
    pair = glyph - (glyph % 2)
    return np.concatenate([glyphs[pair], glyphs[pair + 1]], axis=1).astype(np.float32)


def transforms(tile: np.ndarray) -> dict[str, np.ndarray]:
    out = {"identity": tile}

    swapped = tile.copy()
    swapped[:, 0::2], swapped[:, 1::2] = tile[:, 1::2], tile[:, 0::2]
    out["swap pixel pairs (nibble order)"] = swapped

    # treat the 16-byte-wide, 16-row tile as swizzled in 16x8 byte blocks
    packed = ((tile[:, 0::2].astype(np.uint8) << 4) | tile[:, 1::2].astype(np.uint8))
    flat = packed.reshape(-1)
    import texpack
    unswizzled = texpack.unswizzle(flat, 16, 16).astype(np.uint8)
    wide = np.empty((16, 32), dtype=np.float32)
    wide[:, 0::2] = unswizzled >> 4
    wide[:, 1::2] = unswizzled & 0x0F
    out["unswizzle 16x8"] = wide

    out["halves swapped"] = np.concatenate([tile[:, 16:], tile[:, :16]], axis=1)
    out["rows 8-15 then 0-7"] = np.concatenate([tile[8:], tile[:8]], axis=0)
    return out


def score(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float((a * b).sum() / (na * nb)) if na and nb else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", type=Path, required=True, help="PPSSPP-dumped 32x16 PNG")
    parser.add_argument("--glyph", type=int, default=107)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    uploaded = np.asarray(Image.open(args.dump).convert("RGBA"))[..., 3].astype(np.float32)
    uploaded = uploaded / 255.0 * 15.0
    written = tile_of(BUILD_STREAM, args.glyph)
    original = tile_of(ORIG_STREAM, args.glyph)

    print(f"uploaded {uploaded.shape}, written {written.shape}")
    print("\ncandidate transforms of what we wrote, vs what was uploaded:")
    results = []
    for label, candidate in transforms(written).items():
        whole = score(candidate, uploaded)
        control = score(candidate[:, :16], uploaded[:, :16])
        patched = score(candidate[:, 16:], uploaded[:, 16:])
        results.append((whole, label, control, patched))
        print(f"   {label:34s} whole={whole:+.3f} control_half={control:+.3f} patched_half={patched:+.3f}")

    print("\nfor reference, the untouched original tile vs uploaded:")
    print(f"   original                          whole={score(original, uploaded):+.3f} "
          f"control_half={score(original[:, :16], uploaded[:, :16]):+.3f}")

    if args.out:
        rows = [uploaded, written] + [c for _, c in transforms(written).items()]
        labels = ["uploaded", "written"] + list(transforms(written))
        sheet = np.zeros((len(rows) * 19, 32), dtype=np.uint8)
        for i, row in enumerate(rows):
            sheet[i * 19 : i * 19 + 16, :] = np.clip(row * 17, 0, 255).astype(np.uint8)
        Image.fromarray(sheet, "L").resize((320, sheet.shape[0] * 10), Image.NEAREST).save(args.out)
        for i, label in enumerate(labels):
            print(f"   row {i}: {label}")


if __name__ == "__main__":
    main()

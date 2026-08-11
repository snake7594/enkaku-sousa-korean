"""Encode a texture back into the stream's format -- the inverse of texpack.decode.

Written as a strict mirror of the decoder rather than from the format description, because
the one part that is easy to get wrong is the swizzle, and the decoder already has it right:

    blocks = buf[:byte_width*height].reshape(block_rows, blocks_per_row, 8, 16)
    plane  = blocks.transpose(0, 2, 1, 3).reshape(height, byte_width)

transpose(0, 2, 1, 3) swaps two axes and is its own inverse, so the encoder reshapes the
plane the other way and applies the same transpose.  The 4bpp path packs two pixels per
byte with the left-hand pixel in the low nibble, which is the convention that cost a lot of
time on the font and is worth stating plainly here.

Nothing is trusted until swizzle(unswizzle(x)) == x and encode(decode(t)) == t.image for
every texture in the stream; round_trip() checks exactly that.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

import texpack


def swizzle(plane: np.ndarray, byte_width: int, height: int) -> np.ndarray:
    """Inverse of texpack.unswizzle."""
    if height % 8 or byte_width % 16:
        return plane.reshape(-1)
    block_rows, blocks_per_row = height // 8, byte_width // 16
    blocks = plane.reshape(block_rows, 8, blocks_per_row, 16)
    return blocks.transpose(0, 2, 1, 3).reshape(-1)


def encode_indices(tex: texpack.Texture, indices: np.ndarray,
                   swizzled: bool = True) -> bytes:
    """Pack an index plane back into the texture's stored byte layout."""
    if tex.psm == 4:
        byte_width = tex.width // 2
        packed = np.empty((tex.height, byte_width), dtype=np.uint8)
        # low nibble holds the left-hand pixel
        packed[:, :] = (indices[:, 0::2] & 0x0F) | ((indices[:, 1::2] & 0x0F) << 4)
        plane = packed
    elif tex.psm == 5:
        byte_width = tex.width
        plane = indices.astype(np.uint8)
    else:
        raise ValueError(f"unsupported psm {tex.psm}")
    flat = swizzle(plane, byte_width, tex.height) if swizzled else plane.reshape(-1)
    return flat.tobytes()


def decode_indices(tex: texpack.Texture, swizzled: bool = True) -> np.ndarray | None:
    """The palette indices behind a texture, before the palette is applied."""
    byte_width = tex.width // 2 if tex.psm == 4 else tex.width
    needed = byte_width * tex.height
    buf = np.frombuffer(tex.image, dtype=np.uint8)
    if len(buf) < needed or not needed:
        return None
    plane = (texpack.unswizzle(buf, byte_width, tex.height) if swizzled
             else buf[:needed].reshape(tex.height, byte_width))
    if tex.psm != 4:
        return plane
    out = np.empty((tex.height, tex.width), dtype=np.uint8)
    out[:, 0::2] = plane & 0x0F
    out[:, 1::2] = plane >> 4
    return out


def quantise(image: Image.Image, palette: bytes) -> np.ndarray:
    """Map an RGBA image onto the texture's existing palette by nearest colour.

    The palette is left alone: it is shared with other records and rewriting it would change
    every texture that uses it.
    """
    colours = np.frombuffer(palette, dtype=np.uint8)
    colours = colours[: (len(colours) // 4) * 4].reshape(-1, 4).astype(np.int32)
    pixels = np.asarray(image.convert("RGBA"), dtype=np.int32)
    h, w, _ = pixels.shape
    flat = pixels.reshape(-1, 1, 4)
    # weight alpha heavily so transparent pixels never map to an opaque colour
    weights = np.array([1, 1, 1, 4], dtype=np.int32)
    dist = (((flat - colours[None, :, :]) ** 2) * weights).sum(axis=2)
    return dist.argmin(axis=1).astype(np.uint8).reshape(h, w)


def round_trip(data: bytes, limit: int | None = None) -> dict:
    """Decode then re-encode every texture and compare against the original bytes."""
    textures = texpack.load_textures(data)
    if limit:
        textures = textures[:limit]
    exact = mismatch = skipped = 0
    failures = []
    for tex in textures:
        indices = decode_indices(tex)
        if indices is None or tex.psm not in (4, 5):
            skipped += 1
            continue
        byte_width = tex.width // 2 if tex.psm == 4 else tex.width
        rebuilt = encode_indices(tex, indices)
        original = tex.image[: byte_width * tex.height]
        if rebuilt == original:
            exact += 1
        else:
            mismatch += 1
            if len(failures) < 6:
                differing = sum(1 for a, b in zip(rebuilt, original) if a != b)
                failures.append({"index": tex.index, "psm": tex.psm,
                                 "size": f"{tex.width}x{tex.height}",
                                 "differing_bytes": differing})
    return {"total": len(textures), "exact": exact, "mismatch": mismatch,
            "skipped": skipped, "failures": failures}


if __name__ == "__main__":
    from pathlib import Path

    stream = Path(r"D:\psp\원격수사\build\stream0.bin").read_bytes()
    result = round_trip(stream)
    print(f"{result['total']} textures: {result['exact']} round-trip exactly, "
          f"{result['mismatch']} differ, {result['skipped']} skipped")
    for f in result["failures"]:
        print(f"   tex{f['index']:04d} {f['size']} psm{f['psm']}: "
              f"{f['differing_bytes']} bytes differ")

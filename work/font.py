"""원격수사 글리프 테이블 (16x16 4bpp).

저장 형식
---------
글리프는 **32x16 4bpp 타일** 단위로 저장된다. 타일 하나 = 256바이트 = 16x16 글리프 2개가
가로로 나란히 놓인 것. 게임은 이 타일을 그대로 VRAM에 올리기 때문에 PPSSPP 텍스처 덤프에도
32x16 텍스처로 나타난다. 색은 CLUT이 결정하므로 픽셀값은 커버리지(0~15)일 뿐이다.

한 행은 16바이트: 앞 8바이트가 왼쪽 글리프의 16픽셀, 뒤 8바이트가 오른쪽 글리프의 16픽셀.
바이트 안에서는 상위 니블이 먼저 오는 픽셀이다.

폭이 16바이트인 텍스처라 PSP의 16x8 블록 스위즐은 항등이 되어 별도 처리가 필요 없다.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

TILE_BYTES = 256
GLYPH_W = 16
GLYPH_H = 16


def tiles_to_glyphs(data: bytes, offset: int, count: int | None = None) -> np.ndarray:
    """Return an (n_glyphs, 16, 16) array of 0..15 coverage values."""
    usable = (len(data) - offset) // TILE_BYTES
    if count is not None:
        usable = min(usable, count)
    buf = np.frombuffer(data[offset : offset + usable * TILE_BYTES], dtype=np.uint8)
    rows = buf.reshape(usable, GLYPH_H, 16)          # tile, row, byte
    pixels = np.empty((usable, GLYPH_H, 32), dtype=np.uint8)
    # GU_PSM_T4 puts the left-hand pixel in the LOW nibble
    pixels[:, :, 0::2] = rows & 0x0F
    pixels[:, :, 1::2] = rows >> 4
    left = pixels[:, :, :GLYPH_W]
    right = pixels[:, :, GLYPH_W:]
    glyphs = np.empty((usable * 2, GLYPH_H, GLYPH_W), dtype=np.uint8)
    glyphs[0::2] = left
    glyphs[1::2] = right
    return glyphs


def glyphs_to_tiles(glyphs: np.ndarray) -> bytes:
    """Inverse of tiles_to_glyphs; glyph count must be even."""
    if len(glyphs) % 2:
        raise ValueError("glyph count must be even (glyphs are stored in pairs)")
    pixels = np.concatenate([glyphs[0::2], glyphs[1::2]], axis=2)  # (tiles, 16, 32)
    low = pixels[:, :, 0::2].astype(np.uint8) & 0x0F
    high = pixels[:, :, 1::2].astype(np.uint8) << 4
    return (high | low).tobytes()


def is_glyph_tile(tiles: np.ndarray) -> np.ndarray:
    """Side-bearing test: both glyphs in the tile keep their right-hand column clear."""
    right_a = tiles[:, :, GLYPH_W - 1]
    right_b = tiles[:, :, 2 * GLYPH_W - 1]
    return (right_a < 2).all(axis=1) & (right_b < 2).all(axis=1)


def tile_pixels(data: bytes, offset: int) -> np.ndarray:
    """(n_tiles, 16, 32) pixel view used by the detector."""
    usable = (len(data) - offset) // TILE_BYTES
    buf = np.frombuffer(data[offset : offset + usable * TILE_BYTES], dtype=np.uint8)
    rows = buf.reshape(usable, GLYPH_H, 16)
    pixels = np.empty((usable, GLYPH_H, 32), dtype=np.uint8)
    pixels[:, :, 0::2] = rows >> 4
    pixels[:, :, 1::2] = rows & 0x0F
    return pixels


@dataclass(frozen=True)
class FontBlock:
    path: Path
    offset: int
    tiles: int

    @property
    def glyphs(self) -> int:
        return self.tiles * 2

    @property
    def end(self) -> int:
        return self.offset + self.tiles * TILE_BYTES


def sheet(glyphs: np.ndarray, columns: int = 64, scale: int = 1):
    from PIL import Image

    rows = (len(glyphs) + columns - 1) // columns
    canvas = np.zeros((rows * GLYPH_H, columns * GLYPH_W), dtype=np.uint8)
    for i, glyph in enumerate(glyphs):
        r, c = divmod(i, columns)
        canvas[r * GLYPH_H : (r + 1) * GLYPH_H, c * GLYPH_W : (c + 1) * GLYPH_W] = glyph * 17
    image = Image.fromarray(canvas, "L")
    if scale > 1:
        image = image.resize((canvas.shape[1] * scale, canvas.shape[0] * scale), Image.NEAREST)
    return image

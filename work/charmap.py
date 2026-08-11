"""Build a glyph-index -> Unicode table for the 원격수사 kanji font.

The game's 1368 glyphs are 16x16 hand-tuned bitmaps with no character codes
attached, so the mapping has to be recovered by matching each glyph against every
character a Japanese font can draw.  Candidates are rendered large and box-filtered
down to 16x16 so their grey levels resemble the game's antialiasing, then scored
with zero-mean normalised cross-correlation over a small search of sub-pixel
offsets.

The kana table inside BOOT.BIN is drawn by the same artist in plain gojūon order,
which makes it a labelled validation set: rendering parameters are tuned on it
before the kanji are matched.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import font as fontlib

STREAM = Path(r"D:\psp\원격수사\font_extract\script_stream.bin")
BOOT = Path(r"D:\psp\원격수사\iso_extract\PSP_GAME\SYSDIR\BOOT.BIN")
FONT_OFFSET = 0x80
FONT_TILES = 684

FONT_DIR = Path(r"C:\Windows\Fonts")
CANDIDATE_FONTS = [
    ("msgothic.ttc", 0), ("msgothic.ttc", 1), ("msgothic.ttc", 2),
    ("msmincho.ttc", 0),
    ("meiryo.ttc", 0),
    ("YuGothM.ttc", 0), ("YuGothB.ttc", 0),
]

SIZE = 16
SUPER = 4  # supersampling factor


@dataclass(frozen=True)
class RenderConfig:
    font_file: str
    face: int
    px: int          # rendered em size in supersampled pixels
    dx: float
    dy: float

    def label(self) -> str:
        return f"{self.font_file}#{self.face} px={self.px} dx={self.dx:+.1f} dy={self.dy:+.1f}"


def game_glyphs() -> np.ndarray:
    return fontlib.tiles_to_glyphs(STREAM.read_bytes(), FONT_OFFSET, FONT_TILES).astype(np.float32)


def cp932_candidates() -> list[str]:
    """Every character a Shift-JIS font is expected to carry."""
    chars = []
    seen = set()
    for lead in range(0x81, 0xF0):
        for trail in range(0x40, 0xFD):
            if trail == 0x7F:
                continue
            try:
                ch = bytes([lead, trail]).decode("cp932")
            except UnicodeDecodeError:
                continue
            if len(ch) == 1 and ch not in seen:
                seen.add(ch)
                chars.append(ch)
    return chars


def render_set(chars: list[str], config: RenderConfig) -> np.ndarray:
    path = FONT_DIR / config.font_file
    pil_font = ImageFont.truetype(str(path), config.px, index=config.face)
    big = SIZE * SUPER
    out = np.empty((len(chars), SIZE, SIZE), dtype=np.float32)
    canvas = Image.new("L", (big, big))
    draw = ImageDraw.Draw(canvas)
    for i, ch in enumerate(chars):
        draw.rectangle([0, 0, big, big], fill=0)
        draw.text((config.dx * SUPER, config.dy * SUPER), ch, font=pil_font, fill=255)
        small = canvas.resize((SIZE, SIZE), Image.BOX)
        out[i] = np.asarray(small, dtype=np.float32)
    return out


def zncc_matrix(queries: np.ndarray, templates: np.ndarray) -> np.ndarray:
    """(n_queries, n_templates) correlation matrix."""
    q = queries.reshape(len(queries), -1)
    t = templates.reshape(len(templates), -1)
    q = q - q.mean(axis=1, keepdims=True)
    t = t - t.mean(axis=1, keepdims=True)
    qn = np.linalg.norm(q, axis=1, keepdims=True)
    tn = np.linalg.norm(t, axis=1, keepdims=True)
    qn[qn == 0] = 1
    tn[tn == 0] = 1
    return (q / qn) @ (t / tn).T

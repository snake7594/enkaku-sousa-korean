"""Compare Hangul rendering options for the game's 16x16 4bpp cells.

Readability in game is not the same as readability on a white page: the engine draws
each glyph white with a black outline and a drop shadow, which eats thin strokes.  So
every candidate is shown twice — raw, and composited the way the game does it.

Gulim's embedded bitmap strike is 1-bit; an outline font quantised to 4bpp keeps
antialiasing, which is what the game's own glyphs use.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

GULIM = Path(r"C:\Windows\Fonts\gulim.ttc")
HANGANG = Path(r"D:\psp\타임트레블러즈\SeoulHangangB.ttf")


def render(chars: str, font_path: Path, px: int, dx: float, dy: float,
           face: int | None = None, supersample: int = 1) -> np.ndarray:
    """(n, 16, 16) coverage 0..15."""
    kwargs = {"index": face} if face is not None else {}
    scale = supersample
    pil = ImageFont.truetype(str(font_path), px * scale, **kwargs)
    box = 16 * scale
    out = np.zeros((len(chars), 16, 16), dtype=np.uint8)
    canvas = Image.new("L", (box, box))
    draw = ImageDraw.Draw(canvas)
    for i, ch in enumerate(chars):
        draw.rectangle([0, 0, box, box], fill=0)
        draw.text((dx * scale, dy * scale), ch, font=pil, fill=255)
        small = canvas.resize((16, 16), Image.BOX) if scale > 1 else canvas
        out[i] = (np.asarray(small, dtype=np.uint16) * 15 // 255).astype(np.uint8)
    return out


def as_ingame(glyphs: np.ndarray) -> np.ndarray:
    """White glyph, black outline, drop shadow, over a mid-grey background."""
    n = len(glyphs)
    strip = np.concatenate(list(glyphs), axis=1).astype(np.float32) / 15.0
    h, w = strip.shape
    canvas = np.full((h + 4, w + 4), 0.35, dtype=np.float32)
    alpha = np.zeros_like(canvas)
    alpha[2 : 2 + h, 2 : 2 + w] = strip

    outline = np.zeros_like(canvas)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            outline = np.maximum(outline, np.roll(np.roll(alpha, dy, 0), dx, 1))
    shadow = np.roll(np.roll(alpha, 2, 0), 2, 1) * 0.6

    out = canvas * (1 - shadow) + 0.0 * shadow
    out = out * (1 - outline) + 0.0 * outline
    out = out * (1 - alpha) + 1.0 * alpha
    return (np.clip(out, 0, 1) * 255).astype(np.uint8)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", default="한글패치테스트입니다")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--hangang", type=Path, default=HANGANG)
    parser.add_argument("--scale", type=int, default=4)
    args = parser.parse_args()

    options = [("Gulim strike px16", lambda: render(args.text, GULIM, 16, 0, 0, face=0))]
    for px in (14, 15, 16, 17):
        for dy in (-1, 0, 1):
            options.append((
                f"Hangang B px{px} dy{dy:+d} AA",
                lambda px=px, dy=dy: render(args.text, args.hangang, px, 0, dy, supersample=4),
            ))

    rows = []
    labels = []
    for label, fn in options:
        try:
            glyphs = fn()
        except Exception as exc:  # noqa: BLE001
            print(f"   skip {label}: {exc}")
            continue
        if glyphs.max() == 0:
            continue
        rows.append(as_ingame(glyphs))
        labels.append(f"{label}  ink={(glyphs > 2).mean():.2f} levels={len(np.unique(glyphs))}")

    height = sum(r.shape[0] + 3 for r in rows)
    width = max(r.shape[1] for r in rows)
    sheet = np.zeros((height, width), dtype=np.uint8)
    y = 0
    for row in rows:
        sheet[y : y + row.shape[0], : row.shape[1]] = row
        y += row.shape[0] + 3
    image = Image.fromarray(sheet, "L")
    image.resize((width * args.scale, height * args.scale), Image.NEAREST).save(args.out)
    for i, label in enumerate(labels):
        print(f"   row {i}: {label}")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()

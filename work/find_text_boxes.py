"""Work out where the body text sits on a tutorial page, by finding what is not text.

Counting colours to find the type did not separate anything: the panel is flat and its
gradient reads as few colours over large areas, so the whole panel came back as one box.  The
screenshots are the opposite -- photographic, many colours in any small patch -- and they are
the only thing on the page that is.  Finding them and subtracting gives the text area, and the
text area is what has to be cleared and redrawn.

The page is otherwise regular: an orange-bordered panel with a heading bar across the top, a
page number in the bottom right, and the body between them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

CELL = 8
PANEL = (8, 8, 391, 190)          # the orange-bordered box, the same on every page
HEAD = 36                          # height of the heading bar


def photo_cells(image: Image.Image, min_colours: int = 14) -> np.ndarray:
    px = np.asarray(image.convert("RGBA")).astype(np.int32)
    packed = (px[:, :, 0] << 16) | (px[:, :, 1] << 8) | px[:, :, 2]
    packed[px[:, :, 3] < 24] = -1
    rows, cols = image.height // CELL, image.width // CELL
    mask = np.zeros((rows, cols), dtype=bool)
    for r in range(rows):
        for c in range(cols):
            cell = packed[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL]
            mask[r, c] = len(np.unique(cell)) >= min_colours
    return mask


def photo_box(mask: np.ndarray):
    """The bounding box of the photographic cells, in pixels."""
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    if not len(rows) or not len(cols):
        return None
    return [int(cols[0]) * CELL, int(rows[0]) * CELL,
            int(cols[-1] + 1) * CELL - 1, int(rows[-1] + 1) * CELL - 1]


LEFT = (14, 52, 190, 178)          # where a screenshot sits when there is one


def covered(image: Image.Image, box) -> float:
    """How much of a block is something other than the panel's own ground.

    Counting distinct colours did not separate a screenshot from a block of type -- both come
    out in the low hundreds.  Coverage does, and by a long way: type is thin strokes with the
    panel showing through between them, a screenshot is a solid rectangle of picture.
    """
    px = np.asarray(image.convert("RGB")).astype(np.int32)
    patch = px[box[1]:box[3], box[0]:box[2]].reshape(-1, 3)
    values, counts = np.unique(patch, axis=0, return_counts=True)
    ground = values[counts.argmax()]
    return float((np.abs(patch - ground).sum(axis=1) > 40).mean())


def regions(image: Image.Image):
    """Heading box and body box for one page.

    Cell-by-cell detection kept calling anti-aliased type photographic and swallowed the whole
    panel.  Counting colours over the left block as a whole does separate them, because the
    difference is not subtle: a screenshot there runs to thousands of distinct colours and a
    block of type to a few dozen.
    """
    head = [PANEL[0] + 4, PANEL[1] + 4, PANEL[2] - 90, PANEL[1] + HEAD - 4]
    share = covered(image, LEFT)
    if share > 0.5:
        body = [LEFT[2] + 6, PANEL[1] + HEAD + 6, PANEL[2] - 6, PANEL[3] - 16]
    else:
        body = [PANEL[0] + 6, PANEL[1] + HEAD + 6, PANEL[2] - 6, PANEL[3] - 16]
    return head, body, round(share, 3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--survey", type=Path,
                        default=Path(r"D:\psp\원격수사\build\container_text.json"))
    parser.add_argument("--images", type=Path,
                        default=Path(r"D:\psp\원격수사\build\container_text"))
    parser.add_argument("--size", default="512x256")
    parser.add_argument("--out", type=Path,
                        default=Path(r"D:\psp\원격수사\build\text_boxes.json"))
    parser.add_argument("--preview", type=Path,
                        default=Path(r"D:\psp\원격수사\build\text_boxes.png"))
    parser.add_argument("--show", type=int, default=6)
    parser.add_argument("--skip", type=int, default=0)
    args = parser.parse_args()

    want = tuple(int(v) for v in args.size.split("x"))
    survey = json.loads(args.survey.read_text(encoding="utf-8"))["images"]
    found, shots = [], []
    for item in survey:
        if tuple(item["size"]) != want:
            continue
        image = Image.open(args.images / f"{item['id']}.png").convert("RGBA")
        head, body, left = regions(image)
        found.append({"id": item["id"], "block": item["block"], "record": item["record"],
                      "head": head, "body": body, "left_colours": left})
        if args.skip <= len(found) - 1 < args.skip + args.show:
            marked = image.copy()
            draw = ImageDraw.Draw(marked)
            draw.rectangle(head, outline=(255, 90, 90, 255))
            draw.rectangle(body, outline=(120, 220, 255, 255))
            shots.append((f"{item['id']} left={left}", marked))

    args.out.write_text(json.dumps({"schema": "enkaku_text_boxes_v2", "images": found},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(found)} pages -> {args.out}")

    if shots:
        w = max(i.width for _, i in shots)
        sheet = Image.new("RGB", (w + 8, sum(i.height + 14 for _, i in shots) + 8), (40, 40, 55))
        dr = ImageDraw.Draw(sheet)
        y = 4
        for label, im in shots:
            bg = Image.new("RGBA", im.size, (40, 40, 55, 255))
            sheet.paste(Image.alpha_composite(bg, im).convert("RGB"), (4, y))
            dr.text((6, y + im.height + 1), label, fill=(190, 190, 210))
            y += im.height + 14
        sheet.save(args.preview)
        print(f"-> {args.preview}")


if __name__ == "__main__":
    main()

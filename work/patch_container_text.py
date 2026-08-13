"""Set the Korean into the 0001 pictures and write them back into the archive.

Everything about the records is preserved: same tiles, same coordinates, same count, same
lengths.  Only the pixels change, so the decompressed stream keeps its size and the archive
keeps its layout.  Each block's header is an MD5 over the block's payload out to the next
block boundary, so it is recomputed; the packed stream is padded back to its original length
first, which keeps every later block exactly where it was.

The ledger names each picture by the block and record it lives in, and gives the boxes to
clear and the Korean to draw in them.  Boxes are cleared to the colour that surrounds them --
transparent where the picture is transparent, the panel's own dark where it is not -- the same
rule the 0000 label pass settled on.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import decode_container
import encode_container
import lz11_compress
import lzss
import read_blocks
import texenc
import texpack

ROOT = Path(r"D:\psp\원격수사")
FONTS = {
    "serif": Path(r"C:\Windows\Fonts\batang.ttc"),
    "gothic": Path(r"C:\Windows\Fonts\malgunbd.ttf"),
    "gothic-light": Path(r"C:\Windows\Fonts\malgun.ttf"),
}


def load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS.get(name, FONTS["gothic"])), size)


def clear(image: Image.Image, box) -> None:
    """Wipe a box using whatever is around it, so the ground is never guessed."""
    px = np.asarray(image).copy()
    x0, y0, x1, y1 = box
    patch = px[y0:y1 + 1, x0:x1 + 1]
    if (patch[:, :, 3] < 60).mean() > 0.5:
        px[y0:y1 + 1, x0:x1 + 1] = (0, 0, 0, 0)          # the picture is transparent here
    else:
        # Take the ground from inside the box.  Reading it from the pixels beside the box is
        # what the 0000 labels needed, because those sit in a busy strip; here the box often
        # runs the full width of the panel and "beside" is the border or the black outside it,
        # which painted a bar of the wrong colour and left the Japanese showing through.
        # Type is sparse, so the commonest colour in the box is the ground it sits on.
        values, counts = np.unique(patch.reshape(-1, 4), axis=0, return_counts=True)
        px[y0:y1 + 1, x0:x1 + 1] = values[counts.argmax()]
    image.paste(Image.fromarray(px, "RGBA"), (0, 0))


def fit(draw: ImageDraw.ImageDraw, lines, box, font_name: str, start: int) -> tuple:
    """Largest size at which the text fits the box, and where to put it."""
    width = box[2] - box[0] + 1
    height = box[3] - box[1] + 1
    size = start
    while size > 7:
        font = load_font(font_name, size)
        widest = max(draw.textlength(line, font=font) for line in lines)
        step = size + max(2, size // 5)
        if widest <= width and step * len(lines) <= height + step // 2:
            return font, step
        size -= 1
    return load_font(font_name, 8), 10


def draw_text(image: Image.Image, entry) -> None:
    box = entry["box"]
    clear(image, box)
    draw = ImageDraw.Draw(image)
    lines = entry["ko"].split("\n")
    font, step = fit(draw, lines, box, entry.get("font", "gothic"),
                     entry.get("size", box[3] - box[1] + 1))
    colours = entry.get("colours") or [entry.get("colour", "#ffffff")] * len(lines)
    y = box[1] + max(0, ((box[3] - box[1] + 1) - step * len(lines)) // 2)
    for line, colour in zip(lines, colours):
        width = draw.textlength(line, font=font)
        if entry.get("align") == "center":
            x = box[0] + ((box[2] - box[0] + 1) - width) / 2
        elif entry.get("align") == "right":
            x = box[2] - width
        else:
            x = box[0]
        if entry.get("shadow"):
            draw.text((x + 1, y + 1), line, font=font, fill=entry["shadow"])
        if entry.get("bold"):
            # Batang has no bold cut, and the Japanese here is a heavy mincho.  Drawing the
            # same glyphs a pixel apart thickens the strokes without changing their shape.
            for dx, dy in ((1, 0), (0, 1), (1, 1)):
                draw.text((x + dx, y + dy), line, font=font, fill=colour)
        draw.text((x, y), line, font=font, fill=colour)
        y += step


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=ROOT / "work" / "container_ko.json")
    parser.add_argument("--archive", default="0001")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "0001_ko")
    parser.add_argument("--preview", type=Path, default=ROOT / "build" / "container_ko.png")
    parser.add_argument("--chain", type=int, default=128)
    args = parser.parse_args()

    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    work: dict[int, list] = {}
    for item in ledger["images"]:
        work.setdefault(int(item["block"], 16) if isinstance(item["block"], str)
                        else item["block"], []).append(item)

    blob = bytearray((read_blocks.ROOT / args.archive).read_bytes())
    shots, done = [], 0
    for at, items in sorted(work.items()):
        payload = bytes(blob[at + read_blocks.HEADER:])
        plain, _ = read_blocks.open_stream(payload)
        if plain is None:
            raise SystemExit(f"block {at:#x} does not hold an LZ11 stream")
        packed_len = int.from_bytes(payload[1:4], "little")
        _, consumed = lzss.decompress(payload, 0, limit=64 << 20)

        for item in items:
            records = texpack.load_records(plain)
            n = item["record"]
            image, header = decode_container.decode_record(records[n - 1], records[n])
            before = image.copy()
            for entry in item["labels"]:
                draw_text(image, entry)
            plain = encode_container.replace_image(plain, n, image)
            after, _ = decode_container.decode_record(
                texpack.load_records(plain)[n - 1], texpack.load_records(plain)[n])
            shots.append((item["id"], before, after))
            done += 1

        repacked = lz11_compress.compress(plain, max_chain=args.chain)
        if len(repacked) > consumed:
            raise SystemExit(f"block {at:#x}: repacked {len(repacked)} > original {consumed}")
        # Pad back to the original packed length so nothing downstream moves, then redo the
        # block's MD5 over the same span it covered before.
        repacked = repacked + bytes(consumed - len(repacked))
        blob[at + read_blocks.HEADER:at + read_blocks.HEADER + consumed] = repacked
        span_end = ((at + read_blocks.HEADER + consumed + read_blocks.BLOCK - 1)
                    // read_blocks.BLOCK) * read_blocks.BLOCK
        blob[at:at + 0x10] = hashlib.md5(
            bytes(blob[at + read_blocks.HEADER:span_end])).digest()

        check, _ = read_blocks.open_stream(bytes(blob[at + read_blocks.HEADER:]))
        if check != plain:
            raise SystemExit(f"block {at:#x} does not decompress back to what was written")

    args.out.write_bytes(bytes(blob))
    print(f"{done} pictures set in {len(work)} blocks -> {args.out}")
    print(f"   archive {len(blob):,} bytes "
          f"({'same size' if len(blob) == (read_blocks.ROOT / args.archive).stat().st_size else 'SIZE CHANGED'})")

    if shots:
        width = max(b.width for _, b, _ in shots)
        height = sum(b.height * 2 + 10 for _, b, _ in shots) + 8
        sheet = Image.new("RGB", (width + 8, height), (40, 40, 55))
        y = 4
        for _, before, after in shots:
            for image in (before, after):
                bg = Image.new("RGBA", image.size, (40, 40, 55, 255))
                sheet.paste(Image.alpha_composite(bg, image).convert("RGB"), (4, y))
                y += image.height + 2
            y += 6
        sheet.save(args.preview)
        print(f"-> {args.preview}")


if __name__ == "__main__":
    main()

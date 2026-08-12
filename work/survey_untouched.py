"""Show the textures the Korean patch has never written, so the missed ones can be seen.

The save screen still shows 選択 and 決定 in the command bar while 戻る next to them is Korean,
which means the bar is not one texture and the ones nobody looked at are still Japanese.  There
are 449 textures in the archive and the label ledgers name a few dozen.

Patched is decided by comparing the released stream against the original per texture rather
than by trusting the ledgers, since several passes wrote textures without recording them.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import lzss
import texpack
from PIL import Image

ROOT = Path(r"D:\psp\원격수사")
ARCHIVE = ROOT / "iso_extract" / "PSP_GAME" / "USRDIR" / "0000"
STREAM0 = 0x000000


def stream_from(path: Path) -> bytes:
    import iso9660
    if path.suffix.lower() == ".iso":
        record = iso9660.find_record(path.read_bytes(), "/PSP_GAME/USRDIR/0000")
        blob = iso9660.read_file(path, record)
    else:
        blob = path.read_bytes()
    return lzss.decompress(blob, STREAM0)[0]


def sheet(items, columns: int, path: Path, pad: int = 6) -> None:
    if not items:
        return
    width = max(i.width for _, i in items)
    height = max(i.height for _, i in items)
    rows = (len(items) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * (width + pad) + pad,
                               rows * (height + pad + 12) + pad), (18, 18, 28))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(canvas)
    for n, (index, image) in enumerate(items):
        row, col = divmod(n, columns)
        x = pad + col * (width + pad)
        y = pad + row * (height + pad + 12)
        back = Image.new("RGBA", image.size, (18, 18, 28, 255))
        canvas.paste(Image.alpha_composite(back, image).convert("RGB"), (x, y))
        draw.text((x, y + image.height + 1), f"{index}", fill=(150, 150, 170))
    canvas.save(path)
    print(f"   -> {path}  ({len(items)} textures)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--released", type=Path, default=ROOT / "Enkaku_Korean_v3.2.iso")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "untouched")
    parser.add_argument("--columns", type=int, default=6)
    args = parser.parse_args()

    original = stream_from(ARCHIVE)
    released = stream_from(args.released)
    textures = texpack.load_textures(original)
    patched = {t.index: t for t in texpack.load_textures(released)}
    print(f"{len(textures)} textures")

    args.out.mkdir(parents=True, exist_ok=True)
    groups: dict[tuple[int, int], list] = {}
    same = ink = 0
    for tex in textures:
        other = patched.get(tex.index)
        if other is not None and (other.image != tex.image or other.palette != tex.palette):
            continue                                  # the patch already writes this one
        same += 1
        image = texpack.decode(tex)
        if image is None:
            continue
        # Skip textures with nothing in them -- fully transparent, or one flat colour.
        alpha = image.getchannel("A")
        if alpha.getextrema()[1] == 0:
            continue
        extrema = image.convert("RGB").getextrema()
        if all(lo == hi for lo, hi in extrema):
            continue
        ink += 1
        groups.setdefault((tex.width, tex.height), []).append((tex.index, image))

    print(f"{same} never written by the patch, {ink} of them have something in them")
    for (w, h), items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        items.sort()
        sheet(items, args.columns, args.out / f"untouched_{w}x{h}.png")


if __name__ == "__main__":
    main()

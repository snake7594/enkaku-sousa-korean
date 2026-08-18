"""Dump every picture the player can see, as it stands in v3.5, for a full audit.

The report is that patched images still show Japanese underneath, and that untranslated ones
remain.  Judging that needs eyes on every picture, so this writes each one out flattened onto
a dark ground (transparent ink is invisible otherwise) plus index sheets to leaf through.

0000 and 0001 come from the released ISO -- the audit is of what ships, not of the originals.
0002/0003 come from the disc, since nothing in them has ever been patched.
"""
from __future__ import annotations
import json
from pathlib import Path
from PIL import Image, ImageDraw

import iso9660, lzss, texpack, read_blocks, decode_container

ROOT = Path(r"D:\psp\원격수사")
OUT = ROOT / "build" / "audit_v35"
ISO = ROOT / "Enkaku_Korean_v3.5.iso"
BG = (40, 40, 56, 255)


def flat(image: Image.Image) -> Image.Image:
    bg = Image.new("RGBA", image.size, BG)
    return Image.alpha_composite(bg, image.convert("RGBA")).convert("RGB")


def sheets(items, folder: Path, prefix: str, per: int = 12, cell_w: int = 260):
    folder.mkdir(parents=True, exist_ok=True)
    made = []
    for page in range((len(items) + per - 1) // per):
        chunk = items[page * per:(page + 1) * per]
        thumbs = []
        for label, im in chunk:
            if im.width > cell_w:
                im = im.resize((cell_w, max(1, im.height * cell_w // im.width)), Image.LANCZOS)
            thumbs.append((label, im))
        cols = 3
        rows = (len(thumbs) + cols - 1) // cols
        ch = max(i.height for _, i in thumbs) + 16
        sheet = Image.new("RGB", (cols * (cell_w + 8) + 8, rows * ch + 8), BG[:3])
        dr = ImageDraw.Draw(sheet)
        for k, (label, im) in enumerate(thumbs):
            r, c = divmod(k, cols)
            x, y = 8 + c * (cell_w + 8), 8 + r * ch
            sheet.paste(im, (x, y))
            dr.text((x, y + im.height + 2), label, fill=(200, 200, 215))
        p = folder / f"{prefix}_s{page:02d}.png"
        sheet.save(p)
        made.append(str(p))
    return made


manifest = {}

# --- 0000 from the released ISO ---
blob = iso9660.read_file(ISO, iso9660.find_record(ISO.read_bytes(), "/PSP_GAME/USRDIR/0000"))
stream0 = lzss.decompress(blob, 0x000000)[0]
d = OUT / "0000"; d.mkdir(parents=True, exist_ok=True)
items = []
for t in texpack.load_textures(stream0):
    im = texpack.decode(t)
    if im is None or im.getchannel("A").getextrema()[1] == 0:
        continue
    f = flat(im)
    f.save(d / f"tex{t.index:03d}.png")
    items.append((f"tex{t.index:03d} {t.width}x{t.height}", f))
manifest["0000"] = {"count": len(items), "sheets": sheets(items, OUT / "sheets", "0000")}

# --- 0001 from the released ISO ---
blob = iso9660.read_file(ISO, iso9660.find_record(ISO.read_bytes(), "/PSP_GAME/USRDIR/0001"))
d = OUT / "0001"; d.mkdir(parents=True, exist_ok=True)
items = []
for at, payload in read_blocks.blocks(blob):
    plain, _ = read_blocks.open_stream(payload)
    if plain is None:
        continue
    for n, im, h in decode_container.decode_stream(plain):
        f = flat(im)
        f.save(d / f"{at:07x}_{n}.png")
        items.append((f"0001 {at:07x}#{n} {im.width}x{im.height}", f))
manifest["0001"] = {"count": len(items), "sheets": sheets(items, OUT / "sheets", "0001")}

# --- 0002 / 0003 from the disc (never patched) ---
for name, per, cw in (("0002", 24, 130), ("0003", 8, 260)):
    blob = (read_blocks.ROOT / name).read_bytes()
    d = OUT / name; d.mkdir(parents=True, exist_ok=True)
    items = []
    for at, payload in read_blocks.blocks(blob):
        plain, _ = read_blocks.open_stream(payload)
        if plain is None:
            continue
        for n, im, h in decode_container.decode_stream(plain):
            f = flat(im)
            f.save(d / f"{at:07x}_{n}.png")
            items.append((f"{name} {at:07x}#{n}", f))
    manifest[name] = {"count": len(items), "sheets": sheets(items, OUT / "sheets", name, per, cw)}

(OUT / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
for k, v in manifest.items():
    print(k, v["count"], "images,", len(v["sheets"]), "sheets")
print("->", OUT)

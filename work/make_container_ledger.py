"""Start a translation ledger from the pictures themselves.

Each entry gets the box the existing type occupies, measured from the image rather than read
off a ruler by eye -- the same mistake that cost a pass on the HUD strip.  The Korean is left
empty for the entries that need a human decision and filled in for the ones whose wording is
already settled.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(r"D:\psp\원격수사")

# The banners carry one line each and the wording is unambiguous.
BANNERS = {
    "0001_0513800_2": "심문 시작",
    "0001_0514000_2": "심문 종료",
    "0001_0514800_2": "전날의 조사 보고",
}
BANNER_DEFAULT = "보고 종료"


def ink_box(image: Image.Image, pad: int = 2):
    """The box the drawn pixels occupy, with a little room around them."""
    alpha = np.asarray(image)[:, :, 3]
    rows = np.flatnonzero(alpha.max(axis=1) > 24)
    cols = np.flatnonzero(alpha.max(axis=0) > 24)
    if not len(rows) or not len(cols):
        return None
    return [max(0, int(cols[0]) - pad), max(0, int(rows[0]) - pad),
            min(image.width - 1, int(cols[-1]) + pad),
            min(image.height - 1, int(rows[-1]) + pad)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--survey", type=Path, default=ROOT / "build" / "container_text.json")
    parser.add_argument("--images", type=Path, default=ROOT / "build" / "container_text")
    parser.add_argument("--out", type=Path, default=ROOT / "work" / "container_ko_draft.json")
    parser.add_argument("--size", default="256x64")
    args = parser.parse_args()

    want = tuple(int(v) for v in args.size.split("x"))
    survey = json.loads(args.survey.read_text(encoding="utf-8"))["images"]
    entries = []
    for item in survey:
        if tuple(item["size"]) != want:
            continue
        image = Image.open(args.images / f"{item['id']}.png").convert("RGBA")
        box = ink_box(image)
        if box is None:
            continue
        # The banners are centred in a picture much wider than the type, so the box is opened
        # out to the full width: Korean needs a space where the Japanese needed none, and
        # cramping it into the Japanese extent is what shrank it.
        box = [4, box[1], image.width - 5, box[3]]
        entries.append({
            "id": item["id"], "block": item["block"], "record": item["record"],
            "labels": [{"box": box, "ja": "", "ko": BANNERS.get(item["id"], BANNER_DEFAULT),
                        "font": "serif", "align": "center", "colour": "#ffffff",
                        "shadow": "#404040", "bold": True}],
        })

    args.out.write_text(json.dumps({"schema": "enkaku_container_ko_v1", "images": entries},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(entries)} entries -> {args.out}")
    for e in entries[:4]:
        print(f"   {e['id']}  box {e['labels'][0]['box']}  {e['labels'][0]['ko']}")


if __name__ == "__main__":
    main()

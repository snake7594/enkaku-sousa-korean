"""Hunt for a real glyph-index -> character table shipped with the game.

If the developers kept a table anywhere (for the in-game dictionary, for name entry,
or simply left over from the font-subsetting tool), it beats any amount of shape
matching.  Two plausible encodings are searched for:

  * an array of Shift-JIS kanji codes (lead 0x88-0x9F / 0xE0-0xEA, trail 0x40-0xFC)
  * an array of u16 Unicode code points in the CJK range (both endians)

Either would appear as a long run of valid values, which is a very distinctive
signature in binary data.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def sjis_valid(lead: np.ndarray, trail: np.ndarray) -> np.ndarray:
    lead_ok = ((lead >= 0x88) & (lead <= 0x9F)) | ((lead >= 0xE0) & (lead <= 0xEA))
    trail_ok = (trail >= 0x40) & (trail <= 0xFC) & (trail != 0x7F)
    return lead_ok & trail_ok


def unicode_valid(values: np.ndarray) -> np.ndarray:
    return ((values >= 0x4E00) & (values <= 0x9FA5)) | \
           ((values >= 0x3040) & (values <= 0x30FF)) | \
           ((values >= 0xFF00) & (values <= 0xFF9F))


def longest_runs(mask: np.ndarray, min_len: int) -> list[tuple[int, int]]:
    if not mask.any():
        return []
    padded = np.concatenate([[False], mask, [False]])
    edges = np.flatnonzero(padded[1:] != padded[:-1])
    starts, ends = edges[0::2], edges[1::2]
    return [(int(s), int(e)) for s, e in zip(starts, ends) if e - s >= min_len]


def scan(path: Path, min_len: int) -> None:
    data = np.frombuffer(path.read_bytes(), dtype=np.uint8)
    if len(data) < 4:
        return
    reports = []

    for parity in (0, 1):
        body = data[parity:]
        body = body[: (len(body) // 2) * 2].reshape(-1, 2)
        lead, trail = body[:, 0], body[:, 1]

        runs = longest_runs(sjis_valid(lead, trail), min_len)
        for s, e in runs:
            reports.append(("sjis", parity, s * 2 + parity, e - s))

        for label, values in (("u16le", trail.astype(np.uint16) << 8 | lead),
                              ("u16be", lead.astype(np.uint16) << 8 | trail)):
            runs = longest_runs(unicode_valid(values), min_len)
            for s, e in runs:
                reports.append((label, parity, s * 2 + parity, e - s))

    if not reports:
        return
    reports.sort(key=lambda r: -r[3])
    print(f"== {path}")
    for kind, parity, offset, count in reports[:6]:
        print(f"   {kind:6s} parity={parity} at 0x{offset:08x}  {count} entries")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", type=Path, nargs="+")
    parser.add_argument("--min-len", type=int, default=200)
    args = parser.parse_args()

    for root in args.paths:
        targets = sorted(root.rglob("*")) if root.is_dir() else [root]
        for target in targets:
            if target.is_file() and target.stat().st_size >= 1024:
                scan(target, args.min_len)


if __name__ == "__main__":
    main()

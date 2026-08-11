"""Match every game glyph against the cp932 character repertoire and emit a table.

A single rendering configuration is not enough: at 16x16 the game's hand-tuned
bitmaps sit somewhere between the shapes several fonts produce.  So a handful of
good configurations are rendered and their correlations averaged, which is far
more stable than trusting any one of them.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import charmap
from calibrate import KNOWN
from charmap import RenderConfig

# top configurations found by calibrate.py
CONFIGS = [
    RenderConfig("YuGothB.ttc", 0, 60, -0.5, -1.0),
    RenderConfig("YuGothB.ttc", 0, 56, 0.5, -0.5),
    RenderConfig("YuGothB.ttc", 0, 56, 0.0, -0.5),
    RenderConfig("YuGothB.ttc", 0, 52, 0.5, 0.0),
    RenderConfig("msgothic.ttc", 0, 60, -0.5, -1.0),
    RenderConfig("msgothic.ttc", 0, 56, 0.0, -0.5),
    RenderConfig("meiryo.ttc", 0, 60, -0.5, -1.0),
    RenderConfig("msmincho.ttc", 0, 60, -0.5, -1.0),
]


def build_scores(glyphs: np.ndarray, chars: list[str], configs: list[RenderConfig]) -> np.ndarray:
    total = np.zeros((len(glyphs), len(chars)), dtype=np.float32)
    for config in configs:
        rendered = charmap.render_set(chars, config)
        total += charmap.zncc_matrix(glyphs, rendered)
        print(f"   scored {config.label()}")
    return total / len(configs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--topk", type=int, default=5)
    parser.add_argument("--configs", type=int, default=len(CONFIGS))
    args = parser.parse_args()

    glyphs = charmap.game_glyphs()
    chars = charmap.cp932_candidates()
    print(f"{len(glyphs)} game glyphs vs {len(chars)} candidate characters")

    scores = build_scores(glyphs, chars, CONFIGS[: args.configs])
    order = np.argsort(-scores, axis=1)[:, : args.topk]

    # accuracy on the hand-identified glyphs
    hits = top5 = 0
    for index, expected in KNOWN.items():
        ranked = [chars[j] for j in order[index]]
        hits += ranked[0] == expected
        top5 += expected in ranked
        mark = "ok " if ranked[0] == expected else "MISS"
        print(f"   {mark} glyph {index:4d} expected {expected}  got {' '.join(ranked)}")
    print(f"\nknown-glyph accuracy: top1 {hits}/{len(KNOWN)}, top{args.topk} {top5}/{len(KNOWN)}")

    best = scores[np.arange(len(glyphs)), order[:, 0]]
    print(f"confidence: mean {best.mean():.3f}, "
          f">0.6 {(best > 0.6).sum()}, 0.5-0.6 {((best > 0.5) & (best <= 0.6)).sum()}, "
          f"<=0.5 {(best <= 0.5).sum()}")

    if args.out:
        table = []
        for i in range(len(glyphs)):
            table.append({
                "index": i,
                "char": chars[order[i, 0]],
                "score": round(float(scores[i, order[i, 0]]), 4),
                "alts": [chars[j] for j in order[i, 1:]],
            })
        args.out.write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"table -> {args.out}")


if __name__ == "__main__":
    main()

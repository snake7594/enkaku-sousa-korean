"""Print the next slice of the retranslation queue, compactly enough to work from."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

QUEUE = Path(r"D:\psp\원격수사\build\retranslation_queue.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip", type=int, default=4)
    parser.add_argument("--take", type=int, default=10)
    parser.add_argument("--width", type=int, default=130)
    args = parser.parse_args()

    queue = json.loads(QUEUE.read_text(encoding="utf-8"))["queue"]
    for row in queue[args.skip: args.skip + args.take]:
        flat = lambda s: s.replace("\\n", " / ")[: args.width]
        print(f"{row['index']}  ({row['changed_chars']} chars) {row['introduced']}")
        print(f"  OLD-JA {flat(row['before'])}")
        print(f"  NEW-JA {flat(row['after'])}")
        print(f"  KO     {flat(row['current_ko'])}")


if __name__ == "__main__":
    main()

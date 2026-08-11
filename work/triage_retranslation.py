"""Sort the 1,886 changed rows by whether the Korean actually needs redoing.

A changed source line does not always mean a wrong translation.  註都 became 首都, and the
Korean already said 수도 -- the translator read through the corruption.  Elsewhere the
corruption was invisible and the translation followed it: 言っている became 笑っている, and
the Korean says 말하고 which is now simply wrong.

Separating the two is what decides the real workload, and it can be done by asking whether
the corrected character's meaning is already present in the Korean.  Rows where it is get
recorded as no-change; the rest are the actual retranslation queue, ordered by how much of
the line changed so the worst come first.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(r"D:\psp\원격수사")
DIFF = ROOT / "build" / "source_regeneration_diff.json"
OUT = ROOT / "build" / "retranslation_queue.json"

# corrected character -> Korean forms that show the translation already carried its sense
SETTLED = {
    "首": ("수도", "머리", "목"), "取": ("취조", "받", "얻", "쟁취", "잡"),
    "恐": ("송구", "죄송", "두렵", "무섭"), "回": ("이번", "번", "회", "돌"),
    "笑": ("웃",), "術": ("수술", "기술"), "植": ("이식", "심"),
    "防": ("방범", "막", "방지"), "必": ("필연", "반드시", "필요"),
    "再": ("재생", "다시"), "落": ("떨어", "상심", "낙"), "嫌": ("혐의", "싫"),
    "保": ("보존", "보호", "지키"), "互": ("서로", "상호"), "基": ("기초", "따라", "근거"),
    "時": ("시간", "당시", "때", "시"), "間": ("시간", "사이", "간"),
    "三": ("미우라", "삼", "세"), "浦": ("미우라",), "起": ("일으", "일어"),
    "僚": ("관료", "동료"), "鳴": ("울리", "울려"), "触": ("접", "닿", "만지"),
    "勤": ("근무", "부지런"), "動": ("움직", "동"), "親": ("부모", "친"),
}


def main() -> None:
    data = json.loads(DIFF.read_text(encoding="utf-8"))
    changed = data["changed"]

    settled, queue = [], []
    for row in changed:
        before, after, ko = row["before"], row["after"], row.get("current_ko", "")
        # which characters the correction introduced
        introduced = {c for c in after if c not in before}
        covered = [c for c in introduced if c in SETTLED
                   and any(k in ko for k in SETTLED[c])]
        if introduced and len(covered) == len(introduced & set(SETTLED)) and covered:
            settled.append({**row, "resolved_by": covered})
        else:
            queue.append({**row, "introduced": sorted(introduced)[:6],
                          "changed_chars": len(introduced)})

    queue.sort(key=lambda r: -r["changed_chars"])
    OUT.write_text(json.dumps({
        "schema": "enkaku_retranslation_queue_v1",
        "source_diff": str(DIFF),
        "rows_changed": len(changed),
        "already_correct": len(settled),
        "needs_retranslation": len(queue),
        "queue": queue,
        "already_correct_sample": settled[:30],
        "emulator_launched": False,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(changed)} rows changed in the source")
    print(f"   {len(settled)} already read correctly in Korean "
          f"({100.0 * len(settled) / len(changed):.1f}%)")
    print(f"   {len(queue)} need retranslation "
          f"({100.0 * len(queue) / len(changed):.1f}%)")
    top = Counter(c for r in queue for c in r["introduced"])
    print(f"\ncharacters driving the queue: "
          f"{[(c, n) for c, n in top.most_common(10)]}")
    print(f"\nworst rows first:")
    for r in queue[:4]:
        print(f"   {r['index']}  ({r['changed_chars']} chars)")
        print(f"     new  {r['after'][:85]}")
        print(f"     ko   {r['current_ko'][:85]}")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()

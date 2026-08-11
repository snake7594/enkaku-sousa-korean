"""Fill still-pending translation rows with a protected Japanese-to-Korean pass.

This is a generated-draft pass for the Claude-facing translation ledger.  It
does not overwrite existing hand translations.  Names and speaker labels are
temporarily protected before sending short batches to the public translation
endpoint, then restored in Korean.  Rows containing unresolved glyphs remain
marked for review by build_translation_context.py.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "font_extract"
CONTEXT = FONT / "translation_context_for_claude.json"
OVERRIDES = FONT / "translation_overrides.json"
SEP = "ZZSEP9QX"


# Longest first: several entries contain a full name and its shorter form.
PROTECTED = [
    ("斉藤光志", "KOUJI_SAITO"),
    ("斎藤光志", "KOUJI_SAITO"),
    ("水無月幸司", "KOUJI_MINAZUKI"),
    ("水無月葵", "AOI_MINAZUKI"),
    ("水谷朝露", "ASATSUYU_MIZUTANI"),
    ("新城法子", "NORIKO_SHINJO"),
    ("白川一朗", "ICHIRO_SHIRAKAWA"),
    ("白川真二", "SHINJI_SHIRAKAWA"),
    ("白川悟", "SATORU_SHIRAKAWA"),
    ("沼崎慎太郎", "SHINTARO_NUMASAKI"),
    ("加瀬教授", "PROF_KASE"),
    ("順天高等学校", "JUNTEN_HIGH"),
    ("順天高校", "JUNTEN_HIGH"),
    ("水谷探偵事務所", "MIZUTANI_OFFICE"),
    ("探偵倶楽部", "DETECTIVE_CLUB"),
    ("コウちゃん", "KOUCHAN"),
    ("コウジ", "KOUJI"),
    ("法子", "NORIKO"),
    ("光志", "KOUJI"),
    ("朝露", "ASATSUYU"),
    ("水無月", "MINAZUKI"),
    ("葵", "AOI"),
    ("茜", "AKANE"),
    ("美佐恵", "MISAE"),
    ("三浦正信", "MASANOBU_MIURA"),
    ("礼吉", "MIURA"),
    ("一朗", "ICHIRO"),
    ("一臘", "ICHIRO"),
    ("真二", "SHINJI"),
    ("吉本", "YOSHIMOTO"),
    ("近藤", "KONDO"),
    ("東条", "TOJO"),
    ("今林", "IMABAYASHI"),
    ("豊島", "TOYOSHIMA"),
    ("沼崎", "NUMASAKI"),
    ("コウ", "KOUJI"),
]

RESTORE = {
    "KOUJI_SAITO": "사이토 코우지",
    "KOUJI_MINAZUKI": "미나즈키 코우지",
    "AOI_MINAZUKI": "미나즈키 아오이",
    "ASATSUYU_MIZUTANI": "미즈타니 아사츠유",
    "NORIKO_SHINJO": "신조 노리코",
    "ICHIRO_SHIRAKAWA": "시라카와 이치로",
    "SHINJI_SHIRAKAWA": "시라카와 신지",
    "SATORU_SHIRAKAWA": "시라카와 사토루",
    "SHINTARO_NUMASAKI": "누마사키 신타로",
    "PROF_KASE": "가세 교수",
    "JUNTEN_HIGH": "준텐 고등학교",
    "MIZUTANI_OFFICE": "미즈타니 탐정사무소",
    "DETECTIVE_CLUB": "탐정 동아리",
    "KOUCHAN": "코우짱",
    "KOUJI": "코우지",
    "NORIKO": "노리코",
    "ASATSUYU": "아사츠유",
    "MINAZUKI": "미나즈키",
    "AOI": "아오이",
    "AKANE": "아카네",
    "MISAE": "미사에",
    "MASANOBU_MIURA": "미우라 마사노부",
    "MIURA": "미우라",
    "ICHIRO": "이치로",
    "SHINJI": "신지",
    "YOSHIMOTO": "요시모토",
    "KONDO": "콘도",
    "TOJO": "토죠",
    "IMABAYASHI": "이마바야시",
    "TOYOSHIMA": "도요시마",
    "NUMASAKI": "누마사키",
}

SPEAKERS = {
    "法子": "노리코",
    "光志": "코우지",
    "朝露": "아사츠유",
    "葵": "아오이",
    "茜": "아카네",
    "礼吉": "미우라",
    "一朗": "이치로",
    "一臘": "이치로",
    "女性": "여성",
    "女子高生": "여고생",
    "教員": "교원",
    "ドアフォン": "도어폰",
    "敵": "적",
}


def protected(text: str) -> tuple[str, dict[str, str]]:
    replacements: dict[str, str] = {}
    # Ruby is an annotation for the Japanese glyph, not prose to translate.
    # Passing it through the endpoint can duplicate or truncate the sentence.
    result = re.sub(r"《[^》]*》", "", text)
    for source, token in sorted(PROTECTED, key=lambda pair: len(pair[0]), reverse=True):
        if source in result:
            result = result.replace(source, token)
            replacements[token] = RESTORE[token]
    return result, replacements


def restore(text: str, replacements: dict[str, str]) -> str:
    result = text
    for token, korean in sorted(replacements.items(), key=lambda pair: len(pair[0]), reverse=True):
        result = result.replace(token, korean)
    return result


def speaker_fix(source: str, korean: str) -> str:
    first = source.split("\\n", 1)[0]
    match = re.fullmatch(r"【(.+?)】", first)
    if not match:
        return korean
    label = SPEAKERS.get(match.group(1))
    if not label:
        return korean
    lines = korean.split("\\n", 1)
    if lines:
        lines[0] = f"【{label}】"
    return "\\n".join(lines)


def api_translate(query: str) -> str:
    params = urllib.parse.urlencode(
        {"client": "gtx", "sl": "ja", "tl": "ko", "dt": "t", "q": query}
    )
    request = urllib.request.Request(
        "https://translate.googleapis.com/translate_a/single?" + params,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        payload = json.loads(response.read().decode("utf-8"))
    segments = payload[0] if payload and isinstance(payload[0], list) else []
    return "".join(segment[0] for segment in segments if isinstance(segment, list) and segment)


def api_translate_resilient(query: str) -> str:
    """Translate a query, retrying line-by-line if the endpoint truncates it."""
    translated = api_translate(query)
    expected_breaks = query.count("\\n")
    if translated.count("\\n") >= expected_breaks:
        return translated
    pieces = query.split("\\n")
    output: list[str] = []
    for piece in pieces:
        if not piece:
            output.append("")
            continue
        output.append(api_translate(piece).strip())
        time.sleep(0.12)
    return "\\n".join(output)


def split_batches(items: list[tuple[str, str]], max_chars: int) -> list[list[tuple[str, str]]]:
    batches: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    size = 0
    for source, query in items:
        add = len(query) + len(SEP)
        if current and size + add > max_chars:
            batches.append(current)
            current = []
            size = 0
        current.append((source, query))
        size += add
    if current:
        batches.append(current)
    return batches


def translate_items(items: list[tuple[str, str]]) -> dict[str, str]:
    query = SEP.join(query for _, query in items)
    try:
        translated = api_translate(query)
        parts = translated.split(SEP)
        if len(parts) == len(items):
            result = {}
            for (source, original), value in zip(items, parts):
                result[source] = api_translate_resilient(original) if value.count("\\n") < original.count("\\n") else value.strip()
            return result
    except Exception:
        pass

    result: dict[str, str] = {}
    for source, query in items:
        for attempt in range(3):
            try:
                result[source] = api_translate_resilient(query).strip()
                break
            except Exception:
                if attempt == 2:
                    continue
                time.sleep(1.0 + attempt)
        time.sleep(0.15)
    return result


def translate_one(source: str) -> tuple[str, str | None, str | None]:
    query, replacements = protected(source)
    for attempt in range(3):
        try:
            translated = api_translate_resilient(query).strip()
            if not translated:
                raise RuntimeError("empty translation")
            korean = speaker_fix(source, restore(translated, replacements))
            return source, korean, None
        except Exception as exc:  # noqa: BLE001
            if attempt < 2:
                time.sleep(0.7 * (attempt + 1))
            else:
                return source, None, f"{type(exc).__name__}: {exc}"
    return source, None, "unreachable"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-entries", type=int, default=0)
    parser.add_argument("--max-chars", type=int, default=3200)
    parser.add_argument("--refresh-drafts", action="store_true")
    parser.add_argument(
        "--refresh-indices",
        default="",
        help="when refreshing drafts, limit the pass to rows containing these glyph indices",
    )
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--checkpoint", type=int, default=50)
    args = parser.parse_args()
    refresh_indices = {
        int(value.strip())
        for value in args.refresh_indices.split(",")
        if value.strip()
    }

    context = json.loads(CONTEXT.read_text(encoding="utf-8"))
    data = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    by_order = data.setdefault("by_order", {})
    by_text = data.setdefault("by_japanese_applied", {})

    pending_by_text: dict[str, list[int]] = {}
    for entry in context["entries"]:
        order_key = str(entry["order"])
        existing = by_order.get(order_key, {})
        is_draft = str(existing.get("notes", "")).startswith("대량 번역 초안")
        if args.refresh_drafts:
            if not is_draft:
                continue
            if refresh_indices and not refresh_indices.intersection(entry["source"].get("glyph_indices", [])):
                continue
        elif entry["translation"]["status"] != "pending":
            continue
        source = entry["source"]["japanese_applied"]
        if source in by_text and not args.refresh_drafts:
            continue
        pending_by_text.setdefault(source, []).append(int(entry["order"]))

    unique = list(pending_by_text)
    if args.max_entries:
        unique = unique[: args.max_entries]
    target_set = set(unique)
    added = 0
    failed: list[int] = []

    def apply_result(source: str, korean: str) -> int:
        nonlocal added
        by_text[source] = korean
        orders = pending_by_text[source]
        for order in orders:
            key = str(order)
            draft = {
                "korean": korean,
                "notes": "대량 번역 초안. 화자명·주요 고유명사는 보호 후 복원했으며, kanji_review 항목은 문맥 재검토 필요.",
            }
            if key not in by_order or args.refresh_drafts:
                by_order[key] = draft
            added += 1

        return len(orders)

    def checkpoint() -> None:
        data["notes"] = "Model-assisted hand translation overrides plus protected batch translation drafts; all uncertain Kanji remain reviewable in the Claude context."
        OVERRIDES.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    completed = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(translate_one, source): source for source in unique}
        for future in as_completed(futures):
            source, korean, error = future.result()
            if korean is None:
                failed.extend(pending_by_text[source])
            else:
                apply_result(source, korean)
            completed += 1
            if completed % 50 == 0 or completed == len(unique):
                checkpoint()
                print(f"translated {completed}/{len(unique)} unique; added_rows={added}; failed={len(failed)}", flush=True)

    checkpoint()
    print(f"added draft translations: {added}")
    print(f"failed orders: {len(failed)}")
    if failed:
        print("failed sample:", failed[:30])
    print(f"by_order total: {len(by_order)}")
    print(f"by_japanese_applied total: {len(by_text)}")


if __name__ == "__main__":
    main()

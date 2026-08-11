# 원격수사 한글 번역 품질 재검수 지시문

아래 지시를 순서대로 수행하라. 이 작업의 목적은 “한국어 문자열이 들어 있다”는 확인이 아니라, 일본어 원문과 한국어 번역의 의미가 실제로 일치하는지 전수 재검수하는 것이다.

## 1. 작업 범위와 기본 원칙

- 작업 디렉터리는 `D:\psp\원격수사`이다.
- 게임 또는 PPSSPP를 실행하지 마라. 에뮬레이터 검증은 사용자가 직접 한다.
- 원본 ISO, 원본 대사 TSV, 기존 폰트와 기존 최종 산출물을 먼저 보존하라. 원본 파일을 덮어쓰지 마라.
- 이전 검수 보고서에 `0건`, `완료`라고 되어 있어도 그대로 믿지 말고 원문과 번역을 다시 대조하라.
- 단순 문자열 검색 결과를 번역 오류로 확정하지 마라. 반드시 해당 행의 일본어 원문, 앞뒤 문맥, 화자, 장면을 함께 확인하라.
- 일본어를 한국어로 기계적으로 치환하지 마라. 일본어 원문에 충실하되, 한국어 문장으로 자연스럽고 의미가 정확해야 한다.
- 뜻을 확정할 수 없는 한자는 억지로 추측하지 마라. `확정`, `유력`, `미확정`을 구분하고 근거를 남겨라.

## 2. 반드시 읽을 파일

먼저 다음 파일의 형식과 현재 파이프라인을 확인하라.

- `ANALYSIS.md`
- `font_extract/script_full_raw.tsv` — 인덱스와 원본 바이트 기준
- `font_extract/script_full_ja.tsv` — 현재 해독된 일본어 원문
- `build/translation_ko_semantic_checked.tsv` — 현재 적용 대상인 한국어 번역
- `build/translation_ko_clean.tsv` — 이전 번역본과의 차이 확인용
- `font_extract/translation_overrides.json`
- `font_extract/translation_semantic_overrides.json`
- `font_extract/charmap_final.json`
- `font_extract/charmap_additional_confirmed.json`
- `font_extract/unresolved_kanji_audit.json`
- `font_extract/translation_context_for_claude.json`
- `build/runtime_cfg17_semantic_report.json`
- `build/verify_semantic_iso_cfg17.json`
- `work/translation_text.py`
- `work/audit_semantic_translation.py`
- `work/build_runtime_refs.py`
- `work/verify_semantic_iso.py`

현재 적용 대상 TSV가 실제 최종 ISO를 만드는 입력인지 반드시 확인하라. 파일명이 비슷하다는 이유만으로 다른 TSV를 기준으로 삼지 마라.

## 3. 1차 기준선 검사

검수를 시작하기 전에 다음을 계산하고 `build/translation_quality_review_before.json`에 저장하라.

- 일본어 논리 행 수, 한국어 논리 행 수
- 양쪽 인덱스의 일치 여부
- 원문은 있는데 번역이 없는 행
- 번역은 있는데 원문이 없는 행
- 중복 인덱스와 순서가 어긋난 행
- 줄바꿈/연속 행/제어 코드의 보존 여부
- 일본어·중국어 한자·대체문자 `�`·깨진 물음표·호환 자모가 남은 행
- 현재 번역문 중 인코딩할 수 없는 글자

행 수가 이전 기준인 9,626개와 다르면 차이를 숨기지 말고 원인과 변경된 인덱스를 보고하라.

## 4. 일본어 원문과 한국어 번역의 의미 전수 대조

모든 논리 행을 최소 한 번씩 검토하라. 1회에 전부 처리하기 어려우면 인덱스 구간을 나누어 처리하되, 마지막에 반드시 전체 범위를 합쳐라. 각 행을 다음 항목으로 대조하라.

1. 주어·목적어·화자·호칭이 바뀌지 않았는가?
2. 긍정과 부정, 가능·불가능, 의문·명령, 추측·확정이 뒤집히지 않았는가?
3. 과거·현재·미래, 완료·진행·회상 시제가 보존되었는가?
4. 존댓말·반말·거친 말투·독백·내레이션의 말투가 장면과 화자에 맞는가?
5. 인명·지명·기관명·사건명·아이템명이 일관적인가?
6. 숫자·날짜·시간·횟수·순서·나이·금액이 빠지거나 바뀌지 않았는가?
7. 살인·피해자·범인·진범·증언·취조·구류·자살 등 사건의 핵심 의미가 정확한가?
8. 일본어 관용 표현을 단어 단위로 오역하지 않았는가?
9. 원문에 없는 내용을 추가하거나 중요한 내용을 누락하지 않았는가?
10. 문장부호, 말줄임표, 괄호, 효과음, 선택지와 시스템 문구를 잘못 처리하지 않았는가?

특히 이전 작업에서 실제로 발생했던 유형을 원문 조건부로 다시 검사하라. 전역 치환은 금지한다.

- `クビ` → 문맥에 따라 `해고`, `잘리다`, `목` 등을 구분. 이 게임의 해고 의미를 `곰팡이`로 번역하면 안 된다.
- `生徒` → `학생`. `생선` 등으로 오인하지 않는다.
- `勾留` → `구류`, `구금`, `유치` 중 문맥에 맞는 표현. `상어` 등으로 오인하지 않는다.
- `自殺` → `자살`. `자야` 등으로 오인하지 않는다.
- `兄`, `お兄さん` → 화자와 관계에 따라 `오빠` 또는 `형`. `어머니`로 번역하지 않는다.
- `殺人`, `殺害`, `殺す`, `殺される`, `殺める`, `人殺し` → 각각 `살인`, `살해`, `죽이다`, `살해당하다`, `죽이다/죽인 행위`, `사람을 죽인 자` 등 문법과 문맥에 맞게 번역한다.
- `犯人`, `真犯人` → 각각 `범인`, `진범`을 기본으로 하되 문장 역할에 맞춘다.
- 복원된 `取調べ` 계열 글리프가 `蟇調べ`처럼 보이는 경우에도 문맥상 취조·신문인지 확인한다. `숲`, `삼림`, `삼촌`, `모리` 같은 오역을 남기지 않는다.

위 목록에 없는 오역도 찾아야 한다. 위 목록은 검사 시작점일 뿐, 정답 목록이 아니다.

## 5. 미확정 한자와 문자표 재검사

번역문만 보고 한자를 확정하지 말고, 다음 절차로 미확정 글자를 다시 조사하라.

1. `unresolved_kanji_audit.json`에서 미확정 글자별 모든 등장 행을 모은다.
2. 해당 글자의 바이트/슬롯/문자표 상태와 앞뒤 가나·오쿠리가나를 확인한다.
3. 같은 글자가 이미 확정된 다른 문맥에 등장하는지 검색한다.
4. 같은 단어의 반복, 조사, 활용, 사건 문맥, 인물 관계를 비교한다.
5. 필요하면 글리프 이미지와 원본 바이트를 확인한다.
6. 판독 후보, 읽기, 뜻, 근거 행, 신뢰도를 기록한다.

새로 확인된 한자는 기존 `charmap_final.json`을 무분별하게 덮어쓰지 말고 다음 별도 파일에 기록하라.

`font_extract/translation_quality_additional_kanji.json`

각 항목은 최소한 다음 필드를 갖는다.

```json
{
  "glyph_or_byte": "...",
  "candidate_character": "...",
  "reading": "...",
  "meaning": "...",
  "confidence": 0.0,
  "status": "confirmed|probable|unresolved",
  "evidence_indices": [0],
  "evidence_text": ["..."],
  "alternative_candidates": ["..."],
  "translation_impact": "..."
}
```

`confirmed`는 반복 문맥·가나·글리프·사전적 의미가 함께 맞을 때만 사용하라. 단 한 문장만으로 추측한 경우 `probable` 이하로 표시하라.

## 6. 검수 결과와 수정안 저장

검수 결과를 다음 JSON으로 저장하라.

`build/translation_quality_review.json`

다음 구조를 사용하라.

```json
{
  "schema": "enkaku_translation_quality_review_v1",
  "source_files": {},
  "summary": {
    "total_rows": 0,
    "reviewed_rows": 0,
    "issue_count": 0,
    "major_or_blocker_count": 0,
    "uncertain_count": 0,
    "unresolved_kanji_count": 0
  },
  "issues": [
    {
      "index": 0,
      "source_raw": "...",
      "source_ja": "...",
      "current_ko": "...",
      "proposed_ko": "...",
      "category": "semantic|name|term|number|tone|omission|addition|encoding|layout|unresolved_kanji",
      "severity": "blocker|major|minor|uncertain",
      "confidence": 0.0,
      "reason": "...",
      "evidence_indices": [],
      "applied": false,
      "needs_human_review": false
    }
  ]
}
```

수정이 확실한 항목만 별도 오버라이드 파일에 저장하라.

`font_extract/translation_quality_overrides.json`

오버라이드에는 원문 조건을 포함하여, 다른 문장에 잘못 적용되지 않게 하라. 최소 필드:

```json
{
  "source_index": 0,
  "source_ja": "...",
  "old_translation": "...",
  "new_translation": "...",
  "reason": "...",
  "confidence": 0.0
}
```

확신이 부족한 항목은 번역을 임의로 바꾸지 말고 `translation_quality_review.json`에만 기록하라.

## 7. 수정 반영 시 지켜야 할 기술 조건

확정된 수정이 있으면 현재 프로젝트의 기존 번역 파이프라인을 재사용하여 새 결과를 만든다.

- `script_full_raw.tsv`의 인덱스와 원문 바이트를 변경하지 마라.
- 폰트 슬롯의 크기, 글리프 위치, 스위즐, 인코딩 규칙을 변경하지 마라. 이번 작업은 번역 품질 검수이며 폰트 크기 변경 작업이 아니다.
- 기존 줄 폭과 대사창 범위를 지켜라. 긴 한국어 문장은 의미를 훼손하지 않는 선에서 기존 래핑 규칙으로 줄바꿈하라.
- 새 한글 음절을 넣을 때 `korean_slots_full_clean.json`과 현재 인코더를 기준으로 인코딩 가능 여부를 확인하라.
- 인코딩할 수 없는 글자를 다른 글자로 몰래 바꾸지 말고 해당 행을 보고하라.
- `translation_text.py`의 보고서와 기존 `build_runtime_refs.py`/`verify_semantic_iso.py` 흐름을 먼저 이해한 뒤 사용하라. 기존 파이프라인과 무관한 임시 포맷을 만들지 마라.
- 원본 TSV와 원본 ISO는 절대 덮어쓰지 마라.

수정된 번역 TSV는 다음 이름으로 저장하라.

`build/translation_ko_quality_checked.tsv`

## 8. 수정 후 자동 검증

수정본을 만들었다면 다음을 모두 검사하고 결과를 `build/translation_quality_review_after.json`에 추가하라.

- 일본어 논리 행과 한국어 논리 행의 인덱스가 100% 일치
- 누락·중복·순서 불일치 0건
- 일본어·미확정 한자·대체문자·깨진 물음표가 번역 출력에 남지 않음
- 인코딩 실패 0건
- 잘못된 연속 행과 제어 코드 0건
- 줄 폭 초과 및 대사창 밖으로 나갈 가능성이 있는 행 목록
- 새 오버라이드가 의도하지 않은 다른 행에 적용되지 않음
- 이전에 발견된 오역 후보의 원문 조건부 잔여 건수
- 전체 수정 행 수와 미수정 미확정 행 수

런타임 스트림과 ISO까지 재생성하는 경우에만 다음 구조 검증을 추가하라.

- 압축 해제 후 스트림이 번역 TSV와 일치
- 대사 span 수와 번역 행 수 일치
- 텍스트 span 누락·불일치 0건
- 런타임 참조 중복·충돌 0건
- 텍스트 span 겹침 0건
- ISO 크기와 원본 구조 보존 여부

에뮬레이터는 이 검증에 포함하지 마라. `emulator_launched: false`를 보고서에 명시하라.

## 9. 최종 보고 형식

마지막 응답에는 다음을 간결하게 보고하라.

1. 실제 전수 검토 행 수와 전체 행 수
2. 의미 오역·인명/용어 오역·숫자/부정 오역·인코딩·레이아웃 문제별 건수
3. 확정하여 수정한 행 수
4. 새로 확인한 한자 수와 아직 미확정인 한자 수
5. 수정하지 않은 보류 항목과 보류 이유
6. 생성한 파일의 절대 경로
7. 자동 검증 결과와 SHA-256
8. 에뮬레이터를 실행하지 않았다는 사실
9. 정리한 중간 파일 목록

“오류 0건”이라고 보고하려면 반드시 `reviewed_rows == total_rows`와 각 검증 항목의 실제 수치를 함께 제시하라. 단순 검색 결과가 0건이라는 이유로 번역 품질이 완벽하다고 표현하지 마라.

## 10. 중간 파일 정리

작업 완료 후 재생성 가능한 임시 압축 파일, 임시 ISO, 이전 후보 스트림, `__pycache__`, 디버그 덤프만 정리하라.

- 원본 ISO와 원본 대사/문자표는 삭제하지 마라.
- 최종 ISO, 최종 번역 TSV, 검수 JSON, 추가 한자 JSON, 필요한 재현 스크립트는 보존하라.
- 삭제 전 절대 경로를 목록으로 확인하라.
- 가능하면 영구 삭제 대신 휴지통으로 이동하라.
- 정리한 파일과 보존한 최종 파일을 마지막 보고서에 각각 적어라.

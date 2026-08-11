# 원격수사 ~진실을 향한 23일간~ 한글패치

PSP 게임 **원격수사 ~真実への23日間~** (Enkaku Sousa, `UCJS10088`) 한국어 번역 패치입니다.

대사 9,626행과 게임 내 이미지 211장을 한국어로 옮겼습니다.

---

## 패치 방법

### 준비물

| | |
|---|---|
| 원본 ISO | 아래 MD5와 일치하는 일본판 덤프 |
| xdelta | [xdelta3](https://github.com/jmacd/xdelta-gpl/releases) 또는 xdeltaUI |

원본 ISO는 **직접 덤프한 것을 사용**하십시오. 이 저장소는 게임 데이터를 배포하지 않습니다.

### 원본 ISO 확인

패치를 적용하기 전에 반드시 MD5를 확인하십시오. 다르면 패치가 적용되지 않거나 깨진 결과가 나옵니다.

```
파일명   Enkaku Sousa Shinjitsu eno 23nichikan.iso
크기     739,835,904 바이트
MD5      9f9bb5eec3d2c37f184955b591923e1c
```

Windows에서 확인하는 방법:

```
certutil -hashfile "Enkaku Sousa Shinjitsu eno 23nichikan.iso" MD5
```

### 적용

```
xdelta -d -s "Enkaku Sousa Shinjitsu eno 23nichikan.iso" Enkaku_Korean.xdelta Enkaku_Korean.iso
```

xdeltaUI를 쓰는 경우 **Apply Patch** 탭에서 Patch에 `.xdelta`, Source에 원본 ISO를 지정하십시오.

### 결과 확인

```
파일명   Enkaku_Korean.iso
크기     739,835,904 바이트 (원본과 동일)
MD5      e1ae1cdb39255e75eb52e82c7fb8f7e3
```

크기가 원본과 같은 것이 정상입니다. 이 패치는 파일을 추가하거나 옮기지 않고 기존 데이터를 제자리에서 교체합니다.

### 실행

PPSSPP 및 실기(CFW) 모두에서 동작합니다. 별도 설정은 필요 없습니다.

---

## 무엇이 번역되었는가

| 항목 | 분량 |
|---|---|
| 대사 | 9,626행 |
| 조사 질문 | 63장 |
| 메뉴·설정·챕터명 | 85장 |
| 날짜 카드 | 22장 |
| 기소 카운트 | 9장 |
| 인물 관계 라벨 | 21장 |
| 장소명 | 11장 |
| 시스템 메시지 | 6장 |
| 설정 화면·힌트 패널 | 2장 |
| 명함 | 1장 |

### 아직 일본어로 남아 있는 것

- **HUD 표시** (`拘束 N일째`, `メニュー`, `次へ`, 요일) — 여러 문자열이 한 텍스처에 조각으로 붙어 있고 조각 경계가 코드의 UV 좌표에 있어, 잘못 고치면 HUD 전체가 깨집니다
- **신문 기사 2장** — 세로쓰기 밀집 텍스트
- **인물 이름표 20여 장**
- **수첩 1장** — 손글씨

---

## 개발 내역

### 포맷 해석

| | |
|---|---|
| 아카이브 | `PSP_GAME/USRDIR/0000` — LZ11 스트림 2개 + SGXD 사운드뱅크 |
| 스트림0 | UI 텍스처 449장 (T8/T4, 32×32 스위즐 타일) |
| 스트림1 | 폰트 175,104바이트 + 스크립트 |
| 폰트 | 16×16 4bpp, 684타일 × 2 = 1,368 글리프 |
| 글리프 인덱스 | `(리드 − 0x88) × 253 + 트레일` |

### 문자표 복원

초기 문자표에 **중복 배정 423슬롯**이 있었습니다. 서로 다른 글리프가 같은 한자로 해석돼 원문 자체가 깨진 상태였습니다.

449장 글리프를 이미지로 렌더링해 육안 대조한 결과 **248슬롯을 정정**했고, 6,754회분의 오독이 사라졌습니다. 이 과정에서 인명 `播磨`(하리마), 지명 `宮上銀座`(미야카미 긴자), 형사 이름 `三浦`(미우라)가 복원됐습니다. `三浦`는 그전까지 `退職`(퇴직)으로 읽히고 있었습니다.

원문 9,626행 중 **1,886행**이 달라졌습니다.

### 대사 확장

한국어는 일본어의 약 140%를 차지합니다. 텍스트를 늘리려면 스크립트 안의 절대 참조를 모두 다시 계산해야 하고, 이것이 이 프로젝트에서 가장 오래 걸린 부분이었습니다.

### 이미지 패치

텍스처 인코더는 디코더의 역함수로 구현하고 **449장 전부에 대해 왕복 무손실**을 확인한 뒤 사용했습니다. 팔레트는 레코드 간 공유되므로 건드리지 않고, 렌더 결과를 기존 팔레트에 최근접 색으로 매핑합니다. 모든 텍스처가 원본과 같은 바이트 수로 인코딩되므로 스트림 레이아웃이 바뀌지 않습니다.

### 실기 호환

아카이브를 다른 LBA로 옮긴 빌드는 실기에서 `C1-2858-3` 오류가 났습니다. 아카이브가 원본과 같은 크기이므로 **원래 위치에 제자리 교체**하는 방식으로 되돌렸고, 실행 파일(`EBOOT.BIN`, `BOOT.BIN`, `PARAM.SFO`, `UMD_DATA.BIN`)은 일절 수정하지 않습니다.

---

## 저장소 구성

```
work/            도구 일체 (Python)
font_extract/    문자표, 원문 TSV, 루비 정보
build/           번역문 TSV, 검수 보고서, 매니페스트
ANALYSIS.md      포맷 분석 기록 (한국어)
```

### 주요 도구

| 파일 | 역할 |
|---|---|
| `work/lzss.py` · `work/lz11_compress.py` | LZ11 압축/해제 |
| `work/texpack.py` · `work/texenc.py` | 텍스처 디코드/인코드 |
| `work/font.py` · `work/build_korean_font.py` | 폰트 글리프 |
| `work/build_runtime_refs.py` | 대사 확장 및 참조 재계산 |
| `work/rebuild_0000.py` | 아카이브 재빌드 |
| `work/patch_iso_inplace.py` | ISO 제자리 패치 |

### 직접 빌드하기

원본 ISO를 `iso_extract/`로 풀어둔 뒤:

```
python work/build_runtime_refs.py --base build/stream1_ko_font_clean.bin \
    --tsv build/translation_ko_ellipsis.tsv \
    --slots build/korean_slots_full_clean.json \
    --out build/stream1_ko.bin --translation-is-final

python work/rebuild_0000.py --plain0 build/stream0_ko.bin \
    --plain1 build/stream1_ko.bin --chain 128 --out build/0000_ko

python work/patch_iso_inplace.py --iso "원본.iso" --out Enkaku_Korean.iso \
    --replace /PSP_GAME/USRDIR/0000 build/0000_ko
```

---

## 알려진 문제

- 일부 대사에 문장 끝 마침표가 빠져 있습니다
- 일부 대사에 띄어쓰기가 소실된 구간이 있습니다
- 초벌 번역의 어색한 표현이 남아 있습니다
- 원문 일부가 아직 미해독 글리프를 포함합니다

번역 품질 개선은 계속 진행 중입니다.

---

## 라이선스

번역문·도구·문서는 자유롭게 사용하실 수 있습니다. 게임 데이터의 권리는 원저작자에게 있으며, 이 저장소는 게임 데이터를 포함하지 않습니다.

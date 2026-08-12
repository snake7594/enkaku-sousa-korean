사전 화면의 `解説`·`辞典`·`詳細` 세 문구를 한글화했습니다.

## 적용 방법

```
certutil -hashfile "Enkaku Sousa Shinjitsu eno 23nichikan.iso" MD5
```

```
원본 크기   739,835,904 바이트
원본 MD5    9f9bb5eec3d2c37f184955b591923e1c
```

```
xdelta -d -s "Enkaku Sousa Shinjitsu eno 23nichikan.iso" Enkaku_Korean_v3.1.xdelta Enkaku_Korean.iso
```

```
결과 크기   739,835,904 바이트 (원본과 동일)
결과 MD5    ea61c1446fcf2ee06b17724041fa1d60
```

이전 버전에서 갱신하는 경우에도 **원본 ISO에 적용**하십시오.

```
解説 → 해설    辞典 → 사전    詳細 → 상세
```

## 이미지 한글화는 여기서 끝입니다

449장을 원본과 바이트 단위로 비교해 한 장씩 확인했습니다. **더 이상 일본어 글자가 있는 텍스처는 없습니다.**

`USRDIR/0000` 안의 그림 중 남은 것은 두 가지뿐이고, 둘 다 **원문 자체를 읽을 수 없어서** 손대지 않았습니다.

- **신문 본문** — 약 8픽셀 조판입니다. 일본어로도 한글로도 글자로 읽히지 않는 크기라, 읽을 수 없는 지면을 다른 방식으로 읽을 수 없게 만드는 일이 됩니다. 표제는 v2.6에서 했습니다.
- **수첩** — 손글씨가 4~6픽셀로 그려져 있어 무엇이라 적혀 있는지 판독되지 않습니다. 지어내지 않았습니다.

## 텍스처가 아닌 것들

타이틀 메뉴와 세이브 화면의 `セーブ`·`削除`는 그림이 아니라 **실행 파일 안의 문자열**입니다. 문자열은 찾았지만 한자를 아직 못 읽습니다. 조사 내용은 [이슈 #1](https://github.com/snake7594/enkaku-sousa-korean/issues/1)·[#3](https://github.com/snake7594/enkaku-sousa-korean/issues/3)과 [work/TITLE_MENU_FINDINGS.md](https://github.com/snake7594/enkaku-sousa-korean/blob/master/work/TITLE_MENU_FINDINGS.md)에 적어 두었습니다.

시작 시 나오는 면책 문구도 `USRDIR/0000`의 텍스처가 아니고 실행 파일의 게임 인코딩 텍스트에도 없습니다.

## 제보

이상한 번역이나 깨진 이미지는 [이슈](https://github.com/snake7594/enkaku-sousa-korean/issues)로 알려주십시오. 스크린샷과 **게임의 어느 지점인지**를 함께 적어주시면 특정하기 쉽습니다.

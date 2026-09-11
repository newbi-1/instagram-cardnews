# 인스타그램 카드뉴스 MVP

한국어 인스타그램 카드뉴스 생성 도구입니다. KPI는 **조회수**입니다.  
구매자는 **웹 링크만** 열고: 콘셉트 → 글 붙여넣기 → 카드 만들기 → (선택) 인스타 올리기.

## 안내서

- [실행 방법](설명서_실행방법.md) — **웹으로 쓰기(권장)** / zip은 고급·선택
- [인스타 연결](설명서_인스타연결.md) — **판매자용** Meta 토큰 발급 (구매자 화면에는 기술 용어 없음)
- [판매자용](설명서_판매자용.md) — 배포·면책·zip 체크

## 구매자: 웹으로 쓰기

1. Streamlit Community Cloud 등에서 배포된 URL을 엽니다.
2. 콘셉트 칩 → 텍스트 붙여넣기 → **카드 만들기** → 미리보기
3. (선택) 연결 키 붙여넣기 → **연습** 또는 **실제로 올리기**

로컬 간단 실행:

```bash
./run.sh          # 또는 run.bat
# = streamlit run app_simple.py
```

고급(프로필 폴더·탭 UI): `streamlit run app.py`

## Streamlit Community Cloud 배포

저장소: `newbi-1/instagram-cardnews`

1. [share.streamlit.io](https://share.streamlit.io)에서 GitHub 연결
2. Repository `newbi-1/instagram-cardnews`, Branch `main`, Main file `app_simple.py`
3. (선택) App settings → Secrets 에 `.streamlit/secrets.toml.example` 형식의 `IG_ACCESS_TOKEN` / `IG_USER_ID`
4. Deploy — 구매자에게 나온 **공개 URL**만 전달
5. 구매자 UI에서 연결 키를 붙여 넣으면 Secrets보다 UI 값이 우선합니다

`runtime.txt`(Python 3.11), `packages.txt` 포함.

## 기능 (MVP)

| 됨 | 아직 아님 |
|---|---|
| 웹 한 페이지 생성·미리보기 | 자동 카피라이팅/LLM |
| 콘셉트 팩 + 포토 배경 PNG | 비공식 IG 봇 |
| UI에서 연결 키로 발행 (환경파일 불필요) | 스케줄링·분석 |
| 연습 / 실제로 올리기 | Kmong 연동 |

## 콘셉트 팩

`cafe` `shopping` `academy` `clinic` `real_estate` `restaurant` `personal_brand` `custom`  
정의: `src/concepts.py`

## 발행

- 기본은 **연습**(실제 미발행)
- 공식 Meta Graph API만 사용 (이미지 임시 업로드 경로 포함)
- 구매자는 화면의 연결 키만 사용 · `.env`는 판매자/로컬 고급용

## 스모크 테스트

```bash
python scripts/smoke_generate.py
```

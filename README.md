# 인스타그램 카드뉴스 MVP

한국어 인스타그램 카드뉴스 생성 도구입니다. KPI는 **조회수**입니다.  
구매자는 **웹 링크만** 열고: (선택) 설정에서 인스타 연결 → 콘셉트 → 글 붙여넣기 → 카드 만들기 → (선택) 올리기.

## 구매자 UX (앱 안)

- **설정**(사이드바): 연결 키1(토큰) / 연결 키2(계정번호) 붙여넣기·저장 · 연결 상태 표시 · `.env` 불필요
- **도움말**(사이드바): 사용법 / 인스타 연결 / 자주 묻는 질문 — **앱 안에 내장** (md 파일 열 필요 없음)
- 배경 사진: **무료 이미지 소스** (비용 없음) — 화면 하단 안내

아래 md 안내서는 **판매자·백업용**입니다. 일반 구매자는 앱의 설정·도움말만 보면 됩니다.

## 안내서 (판매자 백업)

- [실행 방법](설명서_실행방법.md) — 웹 링크 안내 / zip은 고급·선택
- [인스타 연결](설명서_인스타연결.md) — **판매자용** 키 발급 (구매자 화면에는 기술 용어 없음)
- [판매자용](설명서_판매자용.md) — 배포·면책·zip 체크

## 구매자: 웹으로 쓰기

1. Streamlit Community Cloud 등에서 배포된 URL을 엽니다.
2. (선택) 왼쪽 **설정**에서 연결 키 저장 → 연결 상태 확인
3. 콘셉트 칩 → 텍스트 붙여넣기 → **카드 만들기** → 미리보기
4. (선택) **연습** 또는 **실제로 올리기** (실제 올리기는 설정 연결 필요)

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
5. 구매자는 **설정** UI에서 연결 키를 붙여 넣으면 Secrets보다 UI 값이 우선합니다

`runtime.txt`(Python 3.11), `packages.txt` 포함.

## 기능 (MVP)

| 됨 | 아직 아님 |
|---|---|
| 웹 한 페이지 생성·미리보기 | 자동 카피라이팅/LLM |
| 콘셉트 팩 + 무료 포토 배경 | 비공식 IG 봇 |
| 설정에서 연결 키로 발행 (`.env` 불필요) | 스케줄링·분석 |
| 앱 내 설정·도움말 | Kmong 연동 |
| 연습 / 실제로 올리기 | |

## 콘셉트 팩

`cafe` `shopping` `academy` `clinic` `real_estate` `restaurant` `personal_brand` `custom`  
정의: `src/concepts.py`

## 발행

- 기본은 **연습**(실제 미발행)
- 공식 Meta Graph API만 사용 (이미지 임시 업로드 경로 포함)
- 구매자는 **설정**의 연결 키만 사용 · `.env`는 판매자/로컬 고급용

## 스모크 테스트

```bash
python scripts/smoke_generate.py
```

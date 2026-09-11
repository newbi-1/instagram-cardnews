# 인스타그램 카드뉴스 MVP

한국어 인스타그램 카드뉴스 생성 도구입니다. KPI는 **조회수**입니다.  
구매자는 **웹 링크만** 열고: **로그인** → 설정(주제·본문·인스타) → **주제 골라 카드 만들기**(무료 구글 뉴스 RSS) → 미리보기 → **테스트 / 즉시 / 예약** 발행.

판매자는 메인 화면 **관리자 로그인** 탭(또는 사이드바 **admin**)에서 아이디/비밀번호로 로그인합니다. 계정은 Streamlit Secrets(`ADMIN_USERNAME` + **`ADMIN_PASSWORD_HASH` 권장** / 또는 평문 `ADMIN_PASSWORD`)에만 둡니다. (선택) 예전 `?gate=` 바로가기·이메일 OTP는 기본 off.

## 구매자 UX (앱 안)

- **설정**(사이드바): **본인** 인스타 키(실제 발행 필수) · **주제 최대 5개** · **본문 템플릿**(직접 / AI BYOK) · AI 제공자+본인 API 키 · 마무리 인사
- **본문:** 켜 둔 주제 선택 → **카드 만들기** (Google News RSS, API 키·유료 LLM 없음) · 마지막 장 = **참여유도**
- **발행:** 테스트발행(한도 미차감) / 즉시발행 / 예약발행 · 하루 기본 **3회**(서울 날짜)
- **도움말**(사이드바): 사용법 / 인스타 연결 / 자주 묻는 질문 — **앱 안에 내장**
- 배경 사진: **무료 이미지 소스** (비용 없음)

콘셉트·업종·타겟 칩은 구매자 메인 흐름에서 **제거**되었습니다. (렌더러/RSS 내부는 `custom` 기본값 사용)

아래 md 안내서는 **판매자·백업용**입니다. 일반 구매자는 앱의 설정·도움말만 보면 됩니다.


## 구매자 로그인 / 관리자

| 역할 | 진입 | 인증 |
|---|---|---|
| 구매자 | `app_simple.py` (배포 Main file) | 판매자가 만든 아이디/비밀번호 **필수** |
| 관리자(판매자) | 메인 **관리자 로그인** 탭 또는 사이드바 **admin** (`pages/admin.py`) | Secrets의 `ADMIN_USERNAME` + `ADMIN_PASSWORD_HASH`(권장) 또는 `ADMIN_PASSWORD` |

**관리자 열기 (Cloud)**

1. 앱 URL 열기 → 상단 **관리자 로그인** 탭 (또는 사이드바 **admin**)
2. Secrets에 넣은 아이디/비밀번호로 로그인
3. 구매자별 **하루 발행 한도** 수정 · 오늘 사용량 확인

```text
https://YOURAPP.streamlit.app/   → 「관리자 로그인」탭 또는 사이드바 admin
```

- 구매자: 같은 메인 URL에서 **구매자 로그인** 탭 사용 (관리자 계정과 별개)
- (선택) `ADMIN_GATE` 가 있으면 `?gate=` 바로가기도 동작 (필수 아님)
- (선택) `ADMIN_OTP_ENABLED=1` 일 때만 이메일 OTP

- 로컬 계정/한도: `data/buyers.json` (**깃 제외**)
- 주제·본문 설정: `data/buyer_settings.json` (**깃 제외**)
- 예약 작업: `data/schedules.json` (**깃 제외**)
- Streamlit Cloud Secrets: `ADMIN_USERNAME` + `ADMIN_PASSWORD_HASH`(권장) 또는 `ADMIN_PASSWORD` + `[buyers.buyer1]` (+ 선택 `IG_*`). 예: `.streamlit/secrets.toml.example`
- 실비밀번호·실아이디는 **Secrets / gitignored secrets.toml 에만** — README·커밋·예시에 넣지 마세요.

## 안내서 (판매자 백업)

- [실행 방법](설명서_실행방법.md) — 웹 링크 안내 / zip은 고급·선택
- [인스타 연결](설명서_인스타연결.md) — **판매자용** 키 발급 (구매자 화면에는 기술 용어 없음)
- [판매자용](설명서_판매자용.md) — 배포·면책·한도·zip 체크

## 구매자: 웹으로 쓰기

1. Streamlit Community Cloud 등에서 배포된 URL을 엽니다.
2. 왼쪽 **설정**에서 주제(켜기)·본문 템플릿·(선택) 인스타 연결 키 저장
3. 본문에서 주제 선택 → **카드 만들기** → 미리보기
4. **테스트발행** / **즉시발행** / **예약발행**
5. 오늘 남은 발행 횟수는 화면·설정에 표시됩니다

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
3. App settings → Secrets 에 `ADMIN_USERNAME` + `ADMIN_PASSWORD_HASH`(권장) 또는 `ADMIN_PASSWORD` + 구매자 `[buyers.*]` (+ 선택 `IG_*`). 예: `.streamlit/secrets.toml.example`
4. Deploy — 구매자에게 나온 **공개 URL**만 전달
5. 구매자는 **설정** UI에서 연결 키를 붙여 넣으면 Secrets보다 UI 값이 우선합니다

`runtime.txt`(Python 3.11), `packages.txt` 포함.



## 보안 (공개 GitHub + Streamlit Cloud)

- **코드/깃에 두지 말 것:** `.env`, `.streamlit/secrets.toml`, `data/*.json`(구매자·설정·예약), 실비밀번호·실토큰·실메일
- **Secrets(또는 로컬 gitignored secrets)에만:** `ADMIN_USERNAME`, **`ADMIN_PASSWORD_HASH`(권장)** 또는 평문 `ADMIN_PASSWORD`, 구매자 `[buyers.*]`, (선택) `IG_*` / OTP 키
- **구매자 비밀번호:** 파일에는 솔트 해시만 저장. 관리자 UI Secrets 붙여넣기 블록은 **항상 플레이스홀더** (실비밀번호 미포함)
- **인스타·AI 키:** 구매자별 `data/buyer_settings.json`(gitignore) 또는 세션. UI·관리자 내보내기는 마스킹만. 판매자 Secrets `IG_*`는 데모용 선택
- **로그인:** 세션 기준 실패 횟수 제한(약 5회 → 잠시 대기). 은행급 보안은 아님
- **유출 시:** Secrets/토큰/관리자·구매자 비밀번호 **즉시 교체(rotate)**. 공개 저장소·채팅에 붙여 넣은 값은 폐기
- **Streamlit Community Cloud(무료)** 는 편의용 호스팅이며 **은행·결제급 보안이 아닙니다.** 고가치 계정·고객 PII는 별도 관리를 권장합니다
- 예시는 `your_admin_id` / `buyer1` / `seller@example.com` 만 사용 — 실아이디·실메일 금지

## 기능 (MVP)

| 됨 | 아직 아님 |
|---|---|
| 웹 한 페이지 · 뉴스 RSS 자동 카드 | 유료 LLM 카피 |
| 주제 슬롯 + 본문 템플릿 + 무료 포토 배경 | 비공식 IG 봇 |
| 테스트 / 즉시 / 예약 발행 · 일일 한도 | 상시 백그라운드 스케줄러 |
| 설정에서 연결 키로 발행 (`.env` 불필요) | 분석 대시보드 |
| 앱 내 설정·도움말 | Kmong 연동 |

**예약 한계:** Streamlit Cloud는 앱이 열려 있을 때만 기한 지난 예약을 처리합니다. (상시 워커 없음)

## 발행·한도

- **테스트발행** = dry_run · 인스타 미게시 · **한도 미차감**
- **즉시발행** = 실제 게시(연결 필요) · 성공 시 한도 차감
- **예약발행** = `data/schedules.json` 저장 · 실제 게시 성공 시 한도 차감
- 기본 `daily_publish_limit = 3` (Asia/Seoul 달력일) · 초과 시 「추가 발행은 관리자에게 문의하세요」
- 공식 Meta Graph API만 사용

## 스모크 테스트

```bash
python scripts/smoke_generate.py
python scripts/smoke_auto_news.py
```

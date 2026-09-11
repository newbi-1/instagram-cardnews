# 인스타그램 카드뉴스 MVP

한국어 인스타그램 카드뉴스 생성 도구입니다. KPI는 **조회수**입니다.  
주제·타겟·스타일을 고르고 소스 텍스트를 붙여 넣으면 1080×1080 PNG 슬라이드(5~8장)를 만듭니다.

## 빠른 실행

- `./run.sh` (macOS/Linux) 또는 `run.bat` (Windows)
- 또는:
  1. `python3 -m venv .venv && source .venv/bin/activate` (Windows: `.venv\Scripts\activate`)
  2. `pip install -r requirements.txt`
  3. `.env.example`을 `.env`로 복사 후 필요 시 토큰 입력
  4. `streamlit run app.py`
  5. 브라우저에서 UI: 프로필 → 새 카드뉴스 → 미리보기 → 발행 전 확인

## 비주얼 (무료 스택)

- **배경**: 주제·타겟 관련 무료 사진(loremflickr, API 키 불필요) → `assets/cache/`에 캐시. 실패 시 소프트 그라데이션.
- **폰트**: 번들 Pretendard (OFL) — 부드러운 모던 한글 타이포.
- **레이아웃**: 커버는 풀블리드 포토 + 다크 그라데이션; 본문/CTA는 블러 포토 위 반투명 글래스 카드.
- **스타일 차이**: overlay tint + accent 색으로 clean / bold / soft 구분.
- **AI 이미지(선택)**: 유료 AI/이미지 API는 기본 경로에 없음. 향후 쓰려면 **구매자 본인 API 키(BYOK)** 만 사용.

## 기능 (MVP)

| 됨 | 아직 아님 |
|---|---|
| Pillow로 1080×1080 PNG 생성 | 자동 카피라이팅/LLM |
| 포토 배경 + 글래스 카드 3종 스타일 | 비공식 IG 봇 |
| 프로필 `clients/<name>/` | Kmong 연동 |
| dry-run 발행 stub (기본 ON) | 로컬 파일 직접 업로드 (Graph는 공개 HTTPS URL 필요) |
| 토큰 있을 때 Graph API 캐러셀 경로 | 스케줄링·분석 대시보드 |

## 스타일

- `style.clean` — Navy Guide
- `style.bold` — Violet Checklist
- `style.soft` — Soft Blue Card

## 발행

- 기본은 **dry-run ON** (실제 발행 안 함).
- 실제 발행은 **공식 Meta Graph API**만 사용합니다.
- `IG_ACCESS_TOKEN`, `IG_USER_ID`를 `.env`에 넣고, 이미지 공개 URL(`IG_IMAGE_BASE_URL` 또는 `.url` 사이드카)이 필요합니다.

## 폴더

```
clients/<profile>/profile.json
clients/<profile>/outputs/*.png
assets/fonts/          # Pretendard (OFL)
assets/cache/          # 사진 캐시 (gitignore)
```

샘플 프로필: `clients/demo/`

## 스모크 테스트

```bash
python scripts/smoke_generate.py
```

## 참고

`uspolicyguide24`는 선택 예시일 뿐 필수 의존이 아닙니다.

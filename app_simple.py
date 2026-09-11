"""인스타그램 카드뉴스 — 웹 간단 UI (한 페이지, 구매자 UX)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.auto_copy import apply_caption_template, auto_build_card_inputs
from src.concepts import (
    CONCEPT_IDS,
    audience_chips,
    concept_label,
    normalize_concept_id,
    sample_source,
    topic_chips,
)
from src.presets import STYLES, style_label
from src.profiles import ensure_demo_profile, outputs_dir
from src.publisher import has_ig_credentials, publish_carousel, resolve_ig_credentials
from src.renderer import generate_cardnews

load_dotenv()
ensure_demo_profile()

# Optional Streamlit Cloud secrets → env (Settings UI paste still overrides)
try:
    if "IG_ACCESS_TOKEN" in st.secrets and st.secrets["IG_ACCESS_TOKEN"]:
        import os

        os.environ.setdefault("IG_ACCESS_TOKEN", str(st.secrets["IG_ACCESS_TOKEN"]))
    if "IG_USER_ID" in st.secrets and st.secrets["IG_USER_ID"]:
        import os

        os.environ.setdefault("IG_USER_ID", str(st.secrets["IG_USER_ID"]))
except Exception:
    pass

st.set_page_config(
    page_title="인스타 카드뉴스",
    page_icon="📰",
    layout="centered",
)

# ── session defaults ─────────────────────────────────────
ss = st.session_state
ss.setdefault("last_paths", [])
ss.setdefault("last_meta", {})
ss.setdefault("ig_token", "")
ss.setdefault("ig_user_id", "")
ss.setdefault("concept_id", "cafe")
ss.setdefault("open_settings", False)
ss.setdefault("open_help", False)
ss.setdefault("fixed_caption", "[{주제}] 오늘의 카드뉴스\n\n#카드뉴스 #{주제}")
ss.setdefault("closing_greeting", "오늘도 응원해요 💛 저장해 두고 다시 보세요.")
ss.setdefault("always_include", "")
ss.setdefault("main_topic", "")
ss.setdefault("last_news_titles", [])
ss.setdefault("last_source", "")


def _chip_index(options: list[str], value: str, fallback: int = 0) -> int:
    if value in options:
        return options.index(value)
    return fallback


def _load_ig_from_query() -> None:
    """Optional: ?ig_uid= for non-secret convenience only (token never in URL)."""
    try:
        uid = st.query_params.get("ig_uid", "")
        if uid and not ss.ig_user_id:
            ss.ig_user_id = str(uid)
    except Exception:
        pass


def _persist_ig_uid_to_query() -> None:
    """Keep account number in URL for refresh convenience; never put token in URL."""
    try:
        uid = (ss.ig_user_id or "").strip()
        if uid:
            st.query_params["ig_uid"] = uid
        elif "ig_uid" in st.query_params:
            del st.query_params["ig_uid"]
    except Exception:
        pass


def _ig_connected() -> bool:
    return has_ig_credentials(
        (ss.ig_token or "").strip(),
        (ss.ig_user_id or "").strip(),
    )


def _ig_status_label() -> str:
    if _ig_connected():
        _, u = resolve_ig_credentials(ss.ig_token, ss.ig_user_id)
        masked = ("…" + u[-4:]) if len(u) >= 4 else "연결됨"
        return f"✅ 연결됨 {masked}"
    return "⚪ 아직 연결 안 됨"


def _render_how_to_get_keys() -> None:
    """구매자용: 판매자에게 키 받는 법 + 판매자가 알려 줄 간단 클릭 순서."""
    st.markdown(
        """
**가장 쉬운 방법:** 판매자(안내해 준 분)에게 **연결 키 1·2**를 받아 위에 붙여 넣으세요.

판매자가 키를 만들 때 누르는 순서(참고):

1. 컴퓨터에서 **Meta 개발자 사이트**에 로그인합니다.
2. **앱 만들기**를 누릅니다. (처음이면 안내에 따라 앱 이름만 넣으면 됩니다)
3. 인스타그램 관련 **사용 항목**을 추가합니다.
4. 내 인스타 계정을 **테스터**로 넣고, 인스타 앱/알림에서 **수락**합니다.
5. **로그인·토큰 발급** 화면에서 긴 글(연결 키 1)을 복사합니다.
6. **계정 번호**(연결 키 2, 숫자)를 확인·복사합니다.
7. 이 앱 **설정**에 붙여 넣고 **저장**합니다. 먼저 **연습**으로 확인해 보세요.

> 키는 비밀번호처럼 다루세요. 카톡·깃허브·압축 파일에 넣지 마세요.
"""
    )


def _render_settings_panel() -> None:
    """사이드바 설정: 인스타 연결 + 고정 캡션·인사·고정 문구."""
    st.markdown("### ⚙️ 설정")
    st.caption(_ig_status_label())

    st.markdown("#### 1. 인스타그램 연결")
    st.markdown(
        "인스타에 **직접 올리려면** 아래 두 칸만 채우면 됩니다. "
        "설치·설정 파일(`.env`)은 **필요 없어요.**"
    )

    token_in = st.text_input(
        "연결 키1 (토큰)",
        value=ss.ig_token,
        type="password",
        placeholder="판매자에게 받은 긴 글 붙여 넣기",
        help="비밀번호처럼 긴 연결 글입니다.",
        key="settings_ig_token",
    )
    uid_in = st.text_input(
        "연결 키2 (계정번호)",
        value=ss.ig_user_id,
        placeholder="판매자에게 받은 숫자",
        help="숫자로 된 계정 번호입니다.",
        key="settings_ig_user_id",
    )

    with st.expander("어떻게 받나요?", expanded=False):
        _render_how_to_get_keys()

    c_save, c_clear = st.columns(2)
    with c_save:
        if st.button("저장·연결", type="primary", use_container_width=True, key="btn_ig_save"):
            ss.ig_token = (token_in or "").strip()
            ss.ig_user_id = (uid_in or "").strip()
            _persist_ig_uid_to_query()
            if _ig_connected():
                st.success("연결됐어요. 이제 카드를 만들고 올릴 수 있어요.")
            else:
                st.warning("연결 키1·키2를 모두 넣어 주세요.")
    with c_clear:
        if st.button("연결 끊기", use_container_width=True, key="btn_ig_clear"):
            ss.ig_token = ""
            ss.ig_user_id = ""
            try:
                if "ig_uid" in st.query_params:
                    del st.query_params["ig_uid"]
            except Exception:
                pass
            st.info("연결을 해제했어요.")
            st.rerun()

    if _ig_connected():
        st.success(_ig_status_label())
    else:
        st.info("연결 전에도 **카드 만들기·미리보기**는 가능해요.")

    st.divider()
    st.markdown("#### 2. 글·캡션 기본값")
    st.caption("카드를 올릴 때 항상 쓰는 문구예요. 이 창을 쓰는 동안 기억해요.")

    cap_in = st.text_area(
        "고정 캡션",
        value=ss.fixed_caption,
        height=100,
        help="인스타 업로드 시 항상 쓰는 캡션. `{주제}` 자리에 메인 주제가 들어갑니다.",
        key="settings_fixed_caption",
        placeholder="예: [{주제}] 오늘의 한 줄\n\n#카드뉴스 #{주제}",
    )
    greet_in = st.text_area(
        "마무리 인사",
        value=ss.closing_greeting,
        height=68,
        help="마지막 슬라이드(CTA) 맨 아래에 붙어요.",
        key="settings_closing_greeting",
        placeholder="예: 오늘도 응원해요 💛",
    )
    always_in = st.text_area(
        "항상 넣을 내용",
        value=ss.always_include,
        height=80,
        help="카드 본문에 항상 들어가는 고정 안내(영업시간, 주소, 할인 등).",
        key="settings_always_include",
        placeholder="예: 매일 10–22시 · 주차 2시간 무료",
    )

    if st.button("문구 저장", use_container_width=True, key="btn_copy_save"):
        ss.fixed_caption = (cap_in or "").strip() or ss.fixed_caption
        ss.closing_greeting = (greet_in or "").strip()
        ss.always_include = (always_in or "").strip()
        st.success("고정 캡션·마무리 인사·항상 넣을 내용을 저장했어요.")

    # Keep widgets in sync even without explicit save (buyer UX)
    ss.fixed_caption = (cap_in if cap_in is not None else ss.fixed_caption) or ss.fixed_caption
    ss.closing_greeting = greet_in if greet_in is not None else ss.closing_greeting
    ss.always_include = always_in if always_in is not None else ss.always_include

    st.divider()
    st.caption("이 브라우저 창을 쓰는 동안만 기억해요. 다른 사람과 키를 공유하지 마세요.")


def _render_help_panel() -> None:
    """앱 안 Help: md 파일을 열라고 하지 않음."""
    st.markdown("### ❓ 도움말")
    tab_use, tab_ig, tab_faq = st.tabs(["사용법", "인스타 연결", "자주 묻는 질문"])

    with tab_use:
        st.markdown(
            """
**한 줄 흐름:** 설정(인스타·고정 캡션) → 콘셉트 → **주제** → **자동으로 카드 만들기** → 미리보기 → (선택) 올리기

1. (선택) 왼쪽 **설정**에서 인스타 연결 키를 저장합니다.
2. 설정에서 **고정 캡션** / **마무리 인사** / **항상 넣을 내용**을 적어 둡니다.
3. **콘셉트(업종)** 버튼을 고릅니다.
4. 주제 칩을 고르거나 **메인 주제**를 직접 입력합니다.
5. **자동으로 카드 만들기**를 누릅니다.
   - 무료 **구글 뉴스 RSS**에서 관련 최신 소식을 가져옵니다. (API 키 없음)
   - 헤드라인·요약을 카드 문장으로 정리합니다. (유료 AI 불필요)
   - 마무리 인사는 마지막 장에, 고정 캡션은 올릴 때 사용합니다.
6. 미리보기 확인 후 (선택) **인스타에 올리기**
   - **연습** = 실제로 안 올림
   - **실제로 올리기** = 설정에 저장한 키로 게시

**팁**
- 주제는 짧게 (예: `신메뉴`, `봄 할인`, `수강 모집`).
- 글을 직접 붙여 넣고 싶을 때만 **고급: 직접 글 붙여넣기**를 엽니다.
- 설치·폴더·`.env` 파일은 신경 쓰지 마세요.
"""
        )

    with tab_ig:
        st.markdown(
            """
**구매자:** 판매자에게 **연결 키1(토큰)** / **연결 키2(계정번호)** 를 받아  
왼쪽 **설정**에 붙여 넣고 **저장·연결**만 하면 됩니다.

"""
        )
        _render_how_to_get_keys()
        st.markdown(
            """
**연결 상태**는 설정 맨 위에 ✅ / ⚪ 로 보여요.  
키를 바꿔야 하면 다시 붙여 넣고 저장하거나, **연결 끊기** 후 새로 넣으세요.
"""
        )

    with tab_faq:
        st.markdown(
            """
**Q. 뉴스는 어디서 가져오나요?**  
A. 무료 **Google News RSS**입니다. API 키·결제가 없습니다. 검색 결과에 따라 품질이 달라질 수 있어요.

**Q. AI(유료)를 쓰나요?**  
A. 아니요. 뉴스 제목·요약을 **템플릿**으로 카드 문장에 넣습니다.

**Q. `.env` 파일을 만들어야 하나요?**  
A. 아니요. 일반 사용은 **설정** 화면의 연결 키만 있으면 됩니다.

**Q. 연결 안 했는데 카드를 만들 수 있나요?**  
A. 네. 미리보기까지는 연결 없이 됩니다. 올릴 때만 설정 연결이 필요합니다.

**Q. 배경 사진 비용이 나가나요?**  
A. 아니요. **무료 이미지 소스**를 씁니다. (비용 없음)

**Q. 고정 캡션의 `{주제}`는?**  
A. 메인 주제로 자동 바뀝니다. 예: `[{주제}]` → `[신메뉴]`

**Q. 연습과 실제로 올리기의 차이는?**  
A. 연습은 서버에 올리기만 시뮬레이션하고 인스타에는 안 올라갑니다.  
실제로 올리기는 설정에 저장된 키로 게시합니다.

**Q. 키가 만료됐어요 / 권한 오류가 나요.**  
A. 판매자에게 키 재발급을 요청한 뒤 설정에 다시 저장하세요.  
테스터 수락·비즈니스/크리에이터 계정 여부도 함께 확인해 달라고 하세요.

**Q. 문제가 나면?**  
A. 화면 메시지를 캡처해 판매자에게 보내 주세요.
"""
        )


_load_ig_from_query()

# ── 사이드바: 설정 + 도움말 (항상 보임) ───────────────────
with st.sidebar:
    _render_settings_panel()
    st.divider()
    _render_help_panel()

# ── 본문 ─────────────────────────────────────────────────
st.title("📰 인스타 카드뉴스")
st.caption("주제 고르기 → 자동으로 카드 만들기(최신 뉴스) → 미리보기 → (선택) 인스타에 올리기")

status_cols = st.columns([3, 1])
with status_cols[0]:
    if _ig_connected():
        st.success(f"인스타 {_ig_status_label()} · 설정에서 변경 가능")
    else:
        st.info("인스타 연결은 **선택**이에요. 왼쪽 설정에서 언제든 연결할 수 있어요.")
with status_cols[1]:
    st.caption("설정·도움말 →")

# ── 1. 콘셉트 ───────────────────────────────────────────
st.subheader("1. 콘셉트 고르기")
concept_cols = st.columns(4)
for i, cid in enumerate(CONCEPT_IDS):
    with concept_cols[i % 4]:
        selected = ss.concept_id == cid
        if st.button(
            concept_label(cid),
            key=f"chip_{cid}",
            type="primary" if selected else "secondary",
            use_container_width=True,
        ):
            ss.concept_id = cid

concept_id = normalize_concept_id(ss.concept_id)
st.markdown(f"**선택:** {concept_label(concept_id)}")

topics = topic_chips(concept_id)
audiences = audience_chips(concept_id)

# ── 2. 주제 ─────────────────────────────────────────────
st.subheader("2. 주제 고르기")
st.caption("칩을 누르거나, 아래에 메인 주제를 직접 적어 주세요.")

topic_cols = st.columns(min(len(topics), 4) or 1)
for i, t in enumerate(topics):
    with topic_cols[i % len(topic_cols)]:
        selected_t = (ss.main_topic or "") == t
        if st.button(
            t,
            key=f"topic_chip_{concept_id}_{t}",
            type="primary" if selected_t else "secondary",
            use_container_width=True,
        ):
            ss.main_topic = t

main_topic_in = st.text_input(
    "메인 주제",
    value=ss.main_topic,
    placeholder="예: 신메뉴, 봄 할인, 수강 모집…",
    key="input_main_topic",
)
# Prefer free-text if user typed; keep chip selection otherwise
if main_topic_in is not None:
    ss.main_topic = str(main_topic_in).strip()

with st.expander("자세히 (타겟·스타일)", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        audience = st.selectbox(
            "타겟",
            audiences,
            index=_chip_index(audiences, audiences[0]),
            key="adv_audience",
        )
    with c2:
        style_id = st.selectbox(
            "스타일",
            list(STYLES.keys()),
            format_func=style_label,
            key="adv_style",
        )
    st.caption("기본값은 콘셉트에 맞춰 자동으로 잡혀 있어요. 필요할 때만 바꾸세요.")

audience = ss.get("adv_audience", audiences[0])
style_id = ss.get("adv_style", "style.clean")
if audience not in audiences:
    audience = audiences[0]

# Advanced: optional paste (de-emphasized)
with st.expander("고급: 직접 글 붙여넣기 (선택)", expanded=False):
    source_key = f"source_{concept_id}"
    if source_key not in ss:
        ss[source_key] = sample_source(concept_id)
    st.caption("자동 뉴스 대신, 갖고 있는 글을 그대로 카드로 만들 때 사용해요.")
    manual_source = st.text_area(
        "직접 넣을 글",
        height=160,
        key=source_key,
        placeholder="예: 1. 포인트 한 줄\n2. 다음 포인트\n3. …",
    )
    if st.button("붙여넣은 글로 카드 만들기", use_container_width=True, key="btn_manual_gen"):
        if not (manual_source and str(manual_source).strip()):
            st.warning("글을 붙여 넣어 주세요.")
        else:
            topic_for_gen = ss.main_topic.strip() or topics[0]
            out = outputs_dir("web")
            with st.spinner("카드 만드는 중…"):
                paths = generate_cardnews(
                    topic=topic_for_gen,
                    audience=audience,
                    source=str(manual_source),
                    style_id=style_id,
                    out_dir=out,
                    profile_name="웹",
                    concept_id=concept_id,
                    closing_greeting=ss.closing_greeting or "",
                )
            caption = apply_caption_template(
                ss.fixed_caption, topic_for_gen, extra_blurb=""
            )
            ss.last_paths = [str(p) for p in paths]
            ss.last_source = str(manual_source)
            ss.last_news_titles = []
            ss.last_meta = {
                "topic": topic_for_gen,
                "audience": audience,
                "style_id": style_id,
                "concept_id": concept_id,
                "concept_label": concept_label(concept_id),
                "caption": caption,
                "mode": "manual",
                "query": "",
            }
            st.success(f"{len(paths)}장 준비됐어요 ↓")
            st.rerun()

# ── 3. 자동 만들기 ───────────────────────────────────────
st.subheader("3. 자동으로 카드 만들기")
topic_now = (ss.main_topic or "").strip()
can_auto = bool(topic_now)
if not can_auto:
    st.caption("주제 칩을 고르거나 메인 주제를 입력하면 버튼이 켜져요.")

if st.button(
    "자동으로 카드 만들기",
    type="primary",
    disabled=not can_auto,
    use_container_width=True,
    key="btn_auto_gen",
):
    out = outputs_dir("web")
    with st.spinner("관련 뉴스 찾는 중… 카드 만드는 중…"):
        result = auto_build_card_inputs(
            topic=topic_now,
            audience=audience,
            concept_id=concept_id,
            concept_label=concept_label(concept_id),
            caption_template=ss.fixed_caption,
            always_include=ss.always_include or "",
            closing_greeting=ss.closing_greeting or "",
        )
        for w in result.warnings:
            st.warning(w)
        if result.news_items:
            st.caption(
                "가져온 소식: "
                + " · ".join(n.title[:40] for n in result.news_items[:4])
            )
        paths = generate_cardnews(
            topic=result.topic,
            audience=result.audience,
            source=result.source,
            style_id=style_id,
            out_dir=out,
            profile_name="웹",
            concept_id=concept_id,
            closing_greeting=ss.closing_greeting or "",
        )
    ss.last_paths = [str(p) for p in paths]
    ss.last_source = result.source
    ss.last_news_titles = [n.title for n in result.news_items]
    ss.last_meta = {
        "topic": result.topic,
        "audience": result.audience,
        "style_id": style_id,
        "concept_id": concept_id,
        "concept_label": concept_label(concept_id),
        "caption": result.caption,
        "mode": "auto_news",
        "query": result.query,
    }
    st.success(f"{len(paths)}장 준비됐어요 ↓")

paths = ss.last_paths
meta = ss.last_meta

if paths:
    mode_label = "자동(뉴스)" if meta.get("mode") == "auto_news" else "직접 글"
    st.markdown(
        f"**미리보기** · {meta.get('concept_label', '')} · "
        f"{meta.get('topic', '')} · {meta.get('audience', '')} · {mode_label}"
    )
    if meta.get("query"):
        st.caption(f"검색어: {meta.get('query')}")
    if ss.last_news_titles:
        with st.expander("참고한 뉴스 제목", expanded=False):
            for t in ss.last_news_titles:
                st.markdown(f"- {t}")

    n = len(paths)
    cols = st.columns(min(n, 4))
    for i, p in enumerate(paths):
        with cols[i % len(cols)]:
            if Path(p).exists():
                st.image(p, caption=f"{i+1}/{n}", use_container_width=True)
            else:
                st.error(f"없음: {p}")

    default_caption = meta.get("caption") or apply_caption_template(
        ss.fixed_caption, meta.get("topic", topic_now or topics[0])
    )
    if ss.get("_caption_seed") != default_caption:
        ss._caption_seed = default_caption
        ss.preview_caption = default_caption
    caption = st.text_area(
        "캡션 (설정 고정 캡션 기준 · 올리기 전 수정 가능)",
        height=100,
        key="preview_caption",
    )

    # ── 4. 인스타 올리기 (설정 자격 증명 사용) ───────────
    st.subheader("4. 인스타에 올리기 (선택)")

    if _ig_connected():
        st.success(f"설정 연결 사용 중 · {_ig_status_label()}")
    else:
        st.warning(
            "아직 인스타가 연결되지 않았어요. "
            "**실제로 올리기**를 쓰려면 왼쪽 **설정**에서 연결 키1·키2를 저장해 주세요. "
            "연습은 연결 없이 가능합니다."
        )

    mode = st.radio(
        "올리기 방식",
        ["연습 (실제로 안 올림)", "실제로 올리기"],
        index=0,
        horizontal=True,
    )
    do_real = mode.startswith("실제")
    token_now = (ss.ig_token or "").strip()
    uid_now = (ss.ig_user_id or "").strip()

    if st.button("인스타에 올리기", type="primary", use_container_width=True):
        if do_real and not has_ig_credentials(token_now, uid_now):
            st.error(
                "실제 올리려면 왼쪽 **설정**에서 인스타 연결(연결 키1·키2 저장)이 필요해요. "
                "설정 패널을 열어 키를 붙여 넣은 뒤 다시 눌러 주세요."
            )
            ss.open_settings = True
        else:
            with st.spinner("처리 중…"):
                result = publish_carousel(
                    [Path(p) for p in paths],
                    caption,
                    dry_run=not do_real,
                    access_token=token_now or None,
                    ig_user_id=uid_now or None,
                )
            if result.ok:
                st.success(result.message)
            else:
                st.error(result.message)
            if result.raw and not result.ok:
                with st.expander("문제 해결용 정보 (판매자 전달용)"):
                    st.json(result.raw)
else:
    st.caption("주제를 고르고 **자동으로 카드 만들기**를 누르면 여기에 미리보기가 나타나요.")

st.divider()
st.caption("카드 미리보기만 해도 돼요. 인스타 올리기는 선택 사항입니다.")
st.caption("📷 배경 사진은 무료 이미지 소스 사용 (비용 없음).")

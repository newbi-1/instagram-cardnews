"""인스타그램 카드뉴스 — 웹 간단 UI (한 페이지)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

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

# Optional Streamlit Cloud secrets → env (UI paste still overrides)
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
ss.setdefault("remember_ig", False)


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


_load_ig_from_query()

st.title("📰 인스타 카드뉴스")
st.caption("콘셉트 고르기 → 글 붙여넣기 → 카드 만들기 → (선택) 인스타에 올리기")

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
            # refresh sample source key on concept change
            sample_key = f"source_{cid}"
            if sample_key not in ss:
                ss[sample_key] = sample_source(cid)

concept_id = normalize_concept_id(ss.concept_id)
st.markdown(f"**선택:** {concept_label(concept_id)}")

topics = topic_chips(concept_id)
audiences = audience_chips(concept_id)

# ── 2. 텍스트 ───────────────────────────────────────────
st.subheader("2. 글 붙여넣기")
source_key = f"source_{concept_id}"
if source_key not in ss:
    ss[source_key] = sample_source(concept_id)

source = st.text_area(
    "카드뉴스에 넣을 글을 붙여 넣으세요",
    height=220,
    key=source_key,
    label_visibility="collapsed",
    placeholder="예: 1. 포인트 한 줄\n2. 다음 포인트\n3. …",
)

with st.expander("자세히 (주제·타겟·스타일)", expanded=False):
    c1, c2, c3 = st.columns(3)
    with c1:
        topic = st.selectbox("주제", topics, key="adv_topic")
    with c2:
        audience = st.selectbox(
            "타겟",
            audiences,
            index=_chip_index(audiences, audiences[0]),
            key="adv_audience",
        )
    with c3:
        style_id = st.selectbox(
            "스타일",
            list(STYLES.keys()),
            format_func=style_label,
            key="adv_style",
        )
    st.caption("기본값은 콘셉트에 맞춰 자동으로 잡혀 있어요. 필요할 때만 바꾸세요.")

# defaults when expander not opened yet — widgets still exist after first run
topic = ss.get("adv_topic", topics[0])
audience = ss.get("adv_audience", audiences[0])
style_id = ss.get("adv_style", "style.clean")
if topic not in topics:
    topic = topics[0]
if audience not in audiences:
    audience = audiences[0]

# ── 3. 만들기 ───────────────────────────────────────────
st.subheader("3. 카드 만들기")
can_gen = bool(source and str(source).strip())
if st.button("카드 만들기", type="primary", disabled=not can_gen, use_container_width=True):
    out = outputs_dir("web")
    with st.spinner("카드 만드는 중…"):
        paths = generate_cardnews(
            topic=topic,
            audience=audience,
            source=str(source),
            style_id=style_id,
            out_dir=out,
            profile_name="웹",
            concept_id=concept_id,
        )
    ss.last_paths = [str(p) for p in paths]
    ss.last_meta = {
        "topic": topic,
        "audience": audience,
        "style_id": style_id,
        "concept_id": concept_id,
        "concept_label": concept_label(concept_id),
        "caption": (
            f"[{concept_label(concept_id)}] {topic} · {audience}을(를) 위한 카드뉴스\n\n"
            f"#카드뉴스 #{topic} #{audience} #{concept_label(concept_id)}"
        ),
    }
    st.success(f"{len(paths)}장 준비됐어요 ↓")

paths = ss.last_paths
meta = ss.last_meta

if paths:
    st.markdown(
        f"**미리보기** · {meta.get('concept_label', '')} · "
        f"{meta.get('topic', '')} · {meta.get('audience', '')}"
    )
    # carousel-like: one row scrolling via columns
    n = len(paths)
    cols = st.columns(min(n, 4))
    for i, p in enumerate(paths):
        with cols[i % len(cols)]:
            if Path(p).exists():
                st.image(p, caption=f"{i+1}/{n}", use_container_width=True)
            else:
                st.error(f"없음: {p}")

    caption = st.text_area("캡션 (인스타 올릴 때 사용)", value=meta.get("caption", ""), height=100)

    # ── 4. 인스타 올리기 ─────────────────────────────────
    st.subheader("4. 인스타에 올리기 (선택)")

    token_ui = (ss.ig_token or "").strip()
    uid_ui = (ss.ig_user_id or "").strip()
    creds_ok = has_ig_credentials(token_ui, uid_ui)

    if not creds_ok:
        st.info(
            "인스타에 직접 올리려면 아래 **연결 키** 두 칸만 붙여 넣으면 됩니다. "
            "연결 키는 판매자 안내에 따라 받으세요. (설치·설정 파일 필요 없음)"
        )
        with st.container(border=True):
            st.markdown("**인스타 간단 연결**")
            ss.ig_token = st.text_input(
                "연결 키 1 (비밀번호처럼 긴 글)",
                value=ss.ig_token,
                type="password",
                placeholder="판매자에게 받은 연결 키를 붙여 넣기",
            )
            ss.ig_user_id = st.text_input(
                "연결 키 2 (숫자)",
                value=ss.ig_user_id,
                placeholder="판매자에게 받은 숫자 키",
            )
            st.caption("이 창을 닫기 전까지만 기억해요. 다른 사람에게 공유하지 마세요.")
            if st.button("연결하기", use_container_width=True):
                if has_ig_credentials(ss.ig_token, ss.ig_user_id):
                    st.success("연결됐어요 — 아래에서 올릴 수 있어요.")
                    st.rerun()
                else:
                    st.warning("연결 키 1·2를 모두 넣어 주세요.")
    else:
        t, u = resolve_ig_credentials(token_ui, uid_ui)
        masked = ("…" + u[-4:]) if len(u) >= 4 else "연결됨"
        st.success(f"인스타 연결됨 {masked}")
        if st.button("연결 끊기"):
            ss.ig_token = ""
            ss.ig_user_id = ""
            st.rerun()

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
            st.error("실제 올리려면 위에서 인스타 연결이 필요해요.")
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
    st.caption("카드를 만들면 여기에 미리보기가 나타나요.")

st.divider()
st.caption("카드 미리보기만 해도 돼요. 인스타 올리기는 선택 사항입니다.")

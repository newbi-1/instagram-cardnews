"""인스타그램 카드뉴스 MVP — Streamlit 한국어 UI."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.concepts import (
    CONCEPT_IDS,
    audience_chips,
    concept_label,
    list_concepts,
    normalize_concept_id,
    sample_source,
    topic_chips,
)
from src.presets import STYLES, style_label
from src.profiles import (
    ensure_demo_profile,
    list_profiles,
    load_profile,
    outputs_dir,
    save_profile,
)
from src.publisher import has_ig_credentials, publish_carousel
from src.renderer import generate_cardnews

load_dotenv()
ensure_demo_profile()

st.set_page_config(
    page_title="인스타 카드뉴스 MVP",
    page_icon="📰",
    layout="wide",
)

st.title("📰 인스타그램 카드뉴스 MVP")
st.caption("KPI = 조회수 · 콘셉트 먼저 선택 · 공식 Meta Graph API만 사용 · dry-run 기본 ON")

tabs = st.tabs(["① 내 프로필", "② 새 카드뉴스", "③ 미리보기", "④ 발행 전 확인"])

# session state
if "last_paths" not in st.session_state:
    st.session_state.last_paths = []
if "last_meta" not in st.session_state:
    st.session_state.last_meta = {}


def _concept_index(concept_id: str | None) -> int:
    cid = normalize_concept_id(concept_id)
    try:
        return CONCEPT_IDS.index(cid)
    except ValueError:
        return 0


def _chip_index(options: list[str], value: str, fallback: int = 0) -> int:
    if value in options:
        return options.index(value)
    return fallback


# ─── ① 프로필 ───────────────────────────────────────────
with tabs[0]:
    st.subheader("내 프로필")
    profiles = list_profiles() or ["demo"]
    col1, col2 = st.columns(2)
    with col1:
        selected = st.selectbox("프로필 선택", profiles, index=0)
        profile = load_profile(selected)
        display_name = st.text_input("표시 이름", profile.get("display_name", selected))
        bio = st.text_area("소개", profile.get("bio", ""))
        handle = st.text_input("인스타 핸들", profile.get("instagram_handle", ""))

        concept_options = list_concepts()
        concept_ids = [c[0] for c in concept_options]
        concept_id = st.selectbox(
            "업종/콘셉트 (필수)",
            concept_ids,
            index=_concept_index(profile.get("concept_id")),
            format_func=concept_label,
            help="카드뉴스 톤·사진·주제/타겟 칩이 콘셉트에 맞춰 바뀝니다.",
            key="profile_concept",
        )
        if concept_id == "custom":
            custom_label = st.text_input(
                "직접 입력 콘셉트명",
                value=profile.get("custom_concept_label", ""),
                placeholder="예: 헤어샵, 반려동물, 피트니스…",
            )
        else:
            custom_label = profile.get("custom_concept_label", "")

        pack_topics = topic_chips(concept_id)
        pack_audiences = audience_chips(concept_id)

        default_style = st.selectbox(
            "기본 스타일",
            list(STYLES.keys()),
            format_func=style_label,
            index=list(STYLES.keys()).index(profile.get("default_style", "style.clean"))
            if profile.get("default_style", "style.clean") in STYLES
            else 0,
        )
        default_audience = st.selectbox(
            "기본 타겟",
            pack_audiences,
            index=_chip_index(
                pack_audiences, profile.get("default_audience", pack_audiences[0])
            ),
        )
        if st.button("프로필 저장", type="primary"):
            save_profile(
                selected,
                {
                    "name": selected,
                    "display_name": display_name,
                    "bio": bio,
                    "instagram_handle": handle,
                    "default_style": default_style,
                    "default_audience": default_audience,
                    "concept_id": concept_id,
                    "custom_concept_label": custom_label,
                },
            )
            st.success(f"저장됨: clients/{selected}/profile.json · 콘셉트={concept_label(concept_id)}")
    with col2:
        st.info(
            "프로필은 `clients/<이름>/` 아래에 저장됩니다.\n\n"
            "출력 PNG는 `clients/<이름>/outputs/` 에 생성됩니다.\n\n"
            f"**현재 콘셉트 칩**\n"
            f"- 주제: {', '.join(topic_chips(normalize_concept_id(profile.get('concept_id'))))}\n"
            f"- 타겟: {', '.join(audience_chips(normalize_concept_id(profile.get('concept_id'))))}"
        )
        if selected == "demo":
            st.caption("데모 프로필은 **카페 콘셉트** 샘플입니다.")
        new_name = st.text_input("새 프로필 폴더명 (영문/숫자)")
        if st.button("새 프로필 만들기") and new_name.strip():
            save_profile(
                new_name.strip(),
                {
                    "name": new_name.strip(),
                    "display_name": new_name.strip(),
                    "bio": "",
                    "instagram_handle": "",
                    "default_style": "style.clean",
                    "default_audience": "직장인",
                    "concept_id": "custom",
                    "custom_concept_label": "",
                },
            )
            st.success(f"생성: clients/{new_name.strip()}/")
            st.rerun()

# ─── ② 새 카드뉴스 ───────────────────────────────────────
with tabs[1]:
    st.subheader("새 카드뉴스")
    profiles = list_profiles() or ["demo"]
    profile_name = st.selectbox("사용할 프로필", profiles, key="gen_profile")
    profile = load_profile(profile_name)

    # Concept select at top of generate tab (required before generate)
    gen_concept_id = st.selectbox(
        "업종/콘셉트 (필수)",
        CONCEPT_IDS,
        index=_concept_index(profile.get("concept_id")),
        format_func=concept_label,
        help="생성 전에 콘셉트를 고르세요. 주제·타겟 칩과 훅/CTA/사진 키워드가 바뀝니다.",
        key="gen_concept",
    )
    if gen_concept_id == "custom":
        st.text_input(
            "직접 입력 콘셉트명 (참고용)",
            value=profile.get("custom_concept_label", ""),
            key="gen_custom_label",
            placeholder="예: 헤어샵, 반려동물…",
        )

    gen_topics = topic_chips(gen_concept_id)
    gen_audiences = audience_chips(gen_concept_id)
    st.caption(
        f"**{concept_label(gen_concept_id)}** 콘셉트 · "
        f"주제 {len(gen_topics)}개 · 타겟 {len(gen_audiences)}개"
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        topic = st.selectbox("주제", gen_topics, key="gen_topic")
    with c2:
        aud_default = profile.get("default_audience", gen_audiences[0])
        audience = st.selectbox(
            "타겟",
            gen_audiences,
            index=_chip_index(gen_audiences, aud_default),
            key="gen_audience",
        )
    with c3:
        style_id = st.selectbox(
            "스타일",
            list(STYLES.keys()),
            format_func=style_label,
            index=list(STYLES.keys()).index(profile.get("default_style", "style.clean"))
            if profile.get("default_style", "style.clean") in STYLES
            else 0,
            key="gen_style",
        )

    default_blurb = sample_source(gen_concept_id)
    # Reset source when concept changes so buyers see the matching sample.
    source_key = f"gen_source_{gen_concept_id}"
    if source_key not in st.session_state:
        st.session_state[source_key] = default_blurb
    source = st.text_area(
        "소스 텍스트 (붙여넣기)",
        height=220,
        placeholder="카드뉴스에 넣을 원문·메모·스크립트를 붙여 넣으세요.",
        key=source_key,
    )

    can_generate = bool(gen_concept_id) and bool(source.strip())
    if not gen_concept_id:
        st.warning("콘셉트를 먼저 선택해 주세요.")
    if st.button("슬라이드 생성 (1080×1080 PNG)", type="primary", disabled=not can_generate):
        out = outputs_dir(profile_name)
        with st.spinner("생성 중…"):
            paths = generate_cardnews(
                topic=topic,
                audience=audience,
                source=source,
                style_id=style_id,
                out_dir=out,
                profile_name=profile.get("display_name", profile_name),
                concept_id=gen_concept_id,
            )
        st.session_state.last_paths = [str(p) for p in paths]
        st.session_state.last_meta = {
            "topic": topic,
            "audience": audience,
            "style_id": style_id,
            "profile": profile_name,
            "concept_id": gen_concept_id,
            "concept_label": concept_label(gen_concept_id),
            "caption": (
                f"[{concept_label(gen_concept_id)}] {topic} · {audience}을(를) 위한 카드뉴스\n\n"
                f"#카드뉴스 #{topic} #{audience} #{concept_label(gen_concept_id)}"
            ),
        }
        st.success(f"{len(paths)}장 생성 → {out}")
        st.info("③ 미리보기 탭에서 확인하세요.")

# ─── ③ 미리보기 ─────────────────────────────────────────
with tabs[2]:
    st.subheader("미리보기")
    paths = st.session_state.last_paths
    if not paths:
        st.warning("아직 생성된 슬라이드가 없습니다. ②에서 생성해 주세요.")
    else:
        meta = st.session_state.last_meta
        st.write(
            f"**콘셉트:** {meta.get('concept_label', meta.get('concept_id', '-'))} · "
            f"**주제:** {meta.get('topic')} · **타겟:** {meta.get('audience')} · "
            f"**스타일:** {meta.get('style_id')} · **프로필:** {meta.get('profile')}"
        )
        cols = st.columns(min(4, len(paths)))
        for i, p in enumerate(paths):
            with cols[i % len(cols)]:
                if Path(p).exists():
                    st.image(p, caption=Path(p).name, use_container_width=True)
                else:
                    st.error(f"없음: {p}")

# ─── ④ 발행 전 확인 ─────────────────────────────────────
with tabs[3]:
    st.subheader("발행 전 확인")
    paths = st.session_state.last_paths
    meta = st.session_state.last_meta
    if not paths:
        st.warning("미리볼 슬라이드가 없습니다.")
    else:
        caption = st.text_area(
            "캡션",
            value=meta.get("caption", ""),
            height=120,
        )
        dry_run = st.checkbox(
            "Dry-run (실제 발행 안 함) — 기본 ON",
            value=True,
            help="끄면 공식 Meta Graph API로 발행을 시도합니다. 공개 image_url 필요.",
        )
        creds_ok = has_ig_credentials()
        if creds_ok:
            st.success("IG_ACCESS_TOKEN / IG_USER_ID 감지됨")
        else:
            st.info("자격증명 없음 → dry-run stub만 가능 (.env 참고)")

        st.write(f"슬라이드 {len(paths)}장")
        if st.button("발행 실행", type="primary"):
            result = publish_carousel(
                [Path(p) for p in paths],
                caption,
                dry_run=dry_run,
            )
            if result.ok:
                st.success(result.message)
            else:
                st.error(result.message)
            if result.raw:
                with st.expander("상세"):
                    st.json(result.raw)

st.sidebar.markdown("### 안내")
st.sidebar.markdown(
    "- 콘셉트: 카페 · 쇼핑몰 · 학원 · 병원/클리닉 · 부동산 · 식당 · 개인브랜딩 · 직접 입력\n"
    "- 스타일: Navy Guide / Violet Checklist / Soft Blue Card\n"
    "- 실제 발행: Meta Graph API + 공개 HTTPS 이미지 URL\n"
    "- 비공식 봇·Kmong 연동 없음"
)
st.sidebar.caption("uspolicyguide24 는 선택 예시일 뿐, 필수 아님")

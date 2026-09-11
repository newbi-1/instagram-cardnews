"""관리자 전용 (사이드바 숨김 · URL로만 접근). 구매자 화면에는 링크 없음."""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from src.auth import (
    admin_password_configured,
    create_buyer,
    file_persistence_available,
    list_buyers_rows,
    reset_buyer_password,
    secrets_toml_block,
    secrets_toml_for_new_buyer,
    set_buyer_enabled,
    update_buyer_note,
    verify_admin_password,
)

load_dotenv()

st.set_page_config(page_title="관리자", page_icon="🔐", layout="centered")

ss = st.session_state
ss.setdefault("admin_ok", False)
ss.setdefault("admin_flash", "")

st.title("🔐 관리자")
st.caption("판매자 전용 · 구매자 계정 만들기 / 중지 · 이 주소는 구매자에게 공유하지 마세요.")

if not admin_password_configured():
    st.error(
        "ADMIN_PASSWORD 가 아직 없어요. "
        "로컬은 `.env` 또는 `.streamlit/secrets.toml` 에, "
        "Cloud는 App settings → Secrets 에 `ADMIN_PASSWORD` 를 넣어 주세요."
    )
    st.code('ADMIN_PASSWORD = "강한_비밀번호"', language="toml")
    st.stop()

if not ss.admin_ok:
    pw = st.text_input("관리자 비밀번호", type="password", key="admin_pw_in")
    if st.button("입장", type="primary", use_container_width=True):
        if verify_admin_password(pw or ""):
            ss.admin_ok = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않아요.")
    st.stop()

writable = file_persistence_available()
if writable:
    st.success("로컬 파일 저장 가능 · `data/buyers.json`")
else:
    st.warning(
        "이 환경에서는 파일 저장이 어려울 수 있어요 (Streamlit Cloud 등). "
        "계정을 만든 뒤 아래 **Secrets 붙여넣기 블록**을 Cloud Secrets에 넣어 주세요."
    )

c_out, _ = st.columns([1, 3])
with c_out:
    if st.button("관리자 나가기", use_container_width=True):
        ss.admin_ok = False
        st.rerun()

st.divider()
st.subheader("구매자 계정 만들기")

with st.form("create_buyer_form", clear_on_submit=True):
    new_id = st.text_input("아이디 (영문·숫자)", placeholder="예: cafe_ahn")
    new_pw = st.text_input("비밀번호", type="password", placeholder="4자 이상")
    new_note = st.text_input("메모 (선택)", placeholder="예: 카페 ○○ / 3개월")
    submitted = st.form_submit_button("계정 만들기", type="primary", use_container_width=True)

if submitted:
    ok, msg, record = create_buyer(new_id, new_pw, new_note, persist=writable)
    if ok and writable:
        st.success(f"저장됨: {new_id} — {msg}")
    elif ok and not writable:
        st.info("파일에 못 넣었어요. 아래 블록을 Secrets에 붙여 넣으세요.")
    else:
        st.error(msg)
    if ok:
        block = secrets_toml_for_new_buyer(new_id.strip(), (new_pw or "").strip(), new_note or "")
        st.markdown("**Cloud Secrets에 추가할 블록**")
        st.code(block, language="toml")
        ss["_last_secrets_snippet"] = block

st.divider()
st.subheader("구매자 목록")

rows = list_buyers_rows()
if not rows:
    st.caption("아직 구매자 계정이 없어요.")
else:
    for row in rows:
        u = row["username"]
        with st.expander(
            f"{'✅' if row['enabled'] else '⛔'} {u} · {row['source']}"
            + (f" · {row['note']}" if row["note"] else ""),
            expanded=False,
        ):
            st.write(f"메모: {row['note'] or '(없음)'}")
            st.write(f"출처: {row['source']} · 생성: {row['created_at'] or '—'}")
            note_in = st.text_input("메모 수정", value=row["note"], key=f"note_{u}")
            if st.button("메모 저장", key=f"save_note_{u}"):
                ok, msg = update_buyer_note(u, note_in)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()
            cols = st.columns(3)
            with cols[0]:
                if row["enabled"]:
                    if st.button("사용 중지", key=f"dis_{u}", use_container_width=True):
                        ok, msg = set_buyer_enabled(u, False)
                        (st.success if ok else st.error)(msg)
                        if ok:
                            st.rerun()
                else:
                    if st.button("다시 사용", key=f"en_{u}", use_container_width=True):
                        ok, msg = set_buyer_enabled(u, True)
                        (st.success if ok else st.error)(msg)
                        if ok:
                            st.rerun()
            with cols[1]:
                npw = st.text_input("새 비밀번호", type="password", key=f"npw_{u}")
            with cols[2]:
                if st.button("비밀번호 변경", key=f"rpw_{u}", use_container_width=True):
                    ok, msg = reset_buyer_password(u, npw or "")
                    (st.success if ok else st.error)(msg)

st.divider()
st.subheader("Secrets 붙여넣기 (Cloud용)")
st.caption(
    "Streamlit Cloud → App settings → Secrets 에 붙여 넣으세요. "
    "파일(`data/buyers.json`)은 깃에 올리지 마세요."
)
st.code(secrets_toml_block(include_admin_placeholder=True), language="toml")

st.divider()
st.caption("구매자 화면(메인)에는 관리자 링크를 넣지 않았습니다. 이 페이지 URL만 판매자가 보관하세요.")

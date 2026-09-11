"""Admin console UI — username+password account login + buyer management.

Used by:
- pages/관리자.py (visible sidebar Admin entry)
- app_simple.py optional ?gate= shortcut when ADMIN_GATE is set
"""

from __future__ import annotations

import streamlit as st

from src.auth import (
    admin_account_configured,
    admin_gate_configured,
    admin_otp_enabled,
    authenticate_admin,
    create_buyer,
    file_persistence_available,
    list_buyers_rows,
    reset_buyer_password,
    secrets_toml_block,
    secrets_toml_for_new_buyer,
    set_buyer_enabled,
    update_buyer_note,
    verify_admin_gate,
)
from src.email_otp import (
    can_send_email,
    clear_otp_session,
    email_dev_mode,
    otp_target_hint,
    request_admin_otp,
    verify_otp_code,
)

ADMIN_PAGE_HINT = "사이드바 **관리자** 페이지 (또는 /관리자)"


def query_gate() -> str:
    """Read optional ?gate= from Streamlit query params (string or list)."""
    try:
        qp = st.query_params
    except Exception:
        return ""
    raw = None
    try:
        raw = qp.get("gate")
    except Exception:
        raw = None
    if raw is None:
        return ""
    if isinstance(raw, (list, tuple)):
        return str(raw[0] if raw else "").strip()
    return str(raw).strip()


def show_not_found() -> None:
    """Generic denial — do not hint that admin or auth exists."""
    st.title("페이지 없음")
    st.write("요청하신 페이지를 찾을 수 없습니다.")
    st.caption("Access denied")
    st.stop()


def render_admin_console() -> None:
    """Full admin UI. Primary auth: ADMIN_USERNAME + password/hash. Gate optional."""
    ss = st.session_state
    ss.setdefault("admin_ok", False)
    ss.setdefault("admin_flash", "")

    # Optional legacy gate: if present in URL and configured, must match.
    # Gate is NOT required to open this page.
    gate_param = query_gate()
    if gate_param and admin_gate_configured() and not verify_admin_gate(gate_param):
        show_not_found()

    st.title("🔐 관리자")
    st.caption(
        "판매자 전용 · 아이디/비밀번호 로그인 · "
        "구매자에게 관리자 계정·Secrets를 공유하지 마세요."
    )

    with st.expander("판매자: 관리자 여는 방법", expanded=not ss.admin_ok):
        st.markdown(
            f"""
**구매자 URL** (공유 OK): `https://YOURAPP.streamlit.app/`

**관리자** (공개 페이지 · 로그인 필요):
- Cloud/로컬: 사이드바 **관리자** 메뉴
- 또는 앱 URL의 **관리자** multipage

Secrets 필수 (App settings → Secrets):
- `ADMIN_USERNAME` — 관리자 아이디
- `ADMIN_PASSWORD` — 관리자 비밀번호 (또는 `ADMIN_PASSWORD_HASH`)

선택:
- `ADMIN_GATE` — 예전 `?gate=` 바로가기 (필수 아님)
- `ADMIN_OTP_ENABLED=1` + `ADMIN_EMAIL` + `RESEND_API_KEY` — 이메일 OTP (기본 off)
"""
        )
        if ss.admin_flash:
            st.info(ss.admin_flash)

    if not ss.admin_ok:
        if not admin_account_configured():
            st.error(
                "관리자 계정이 없어요. Secrets에 `ADMIN_USERNAME` 과 "
                "`ADMIN_PASSWORD`(또는 `ADMIN_PASSWORD_HASH`) 를 넣어 주세요."
            )
            st.code(
                'ADMIN_USERNAME = "your_admin_id"\n'
                'ADMIN_PASSWORD = "your_admin_password"\n'
                '# ADMIN_PASSWORD_HASH = "sha256$salt$digest"  # optional',
                language="toml",
            )
            st.stop()

        st.subheader("관리자 로그인")
        st.caption("아이디와 비밀번호로 입장합니다.")
        with st.form("admin_login_form"):
            admin_id = st.text_input("아이디", key="admin_id_in", autocomplete="username")
            admin_pw = st.text_input(
                "비밀번호",
                type="password",
                key="admin_pw_in",
                autocomplete="current-password",
            )
            submitted = st.form_submit_button(
                "로그인", type="primary", use_container_width=True
            )
        if submitted:
            if authenticate_admin(admin_id or "", admin_pw or ""):
                ss.admin_ok = True
                ss.admin_flash = "로그인 완료."
                clear_otp_session(ss)
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 올바르지 않아요.")

        # Optional email OTP (off by default)
        if admin_otp_enabled():
            st.divider()
            st.subheader("이메일 인증 (선택)")
            st.caption(f"등록된 관리자 메일 · {otp_target_hint()}")
            if not can_send_email() and not email_dev_mode():
                st.warning(
                    "RESEND_API_KEY 가 없습니다. "
                    "https://resend.com 에서 키를 발급하거나 OTP를 끄세요."
                )
            if st.button("인증번호 보내기", use_container_width=True):
                ok, msg, dev_code = request_admin_otp(ss)
                if ok:
                    st.success(msg)
                    if dev_code and email_dev_mode():
                        st.code(dev_code, language=None)
                else:
                    st.error(msg)
            code_in = st.text_input("인증번호 6자리", max_chars=6, key="admin_otp_in")
            if st.button("OTP로 입장", use_container_width=True):
                ok, msg = verify_otp_code(ss, code_in or "")
                if ok:
                    ss.admin_ok = True
                    ss.admin_flash = "이메일 인증 완료."
                    st.rerun()
                else:
                    st.error(msg)

        st.stop()

    # --- Authenticated admin UI ---
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
            ss.admin_flash = ""
            clear_otp_session(ss)
            st.rerun()

    st.divider()
    st.subheader("구매자 계정 만들기")

    with st.form("create_buyer_form", clear_on_submit=True):
        new_id = st.text_input("아이디 (영문·숫자)", placeholder="예: cafe_ahn")
        new_pw = st.text_input("비밀번호", type="password", placeholder="4자 이상")
        new_note = st.text_input("메모 (선택)", placeholder="예: 카페 ○○ / 3개월")
        submitted = st.form_submit_button(
            "계정 만들기", type="primary", use_container_width=True
        )

    if submitted:
        ok, msg, _record = create_buyer(new_id, new_pw, new_note, persist=writable)
        if ok and writable:
            st.success(f"저장됨: {new_id} — {msg}")
        elif ok and not writable:
            st.info("파일에 못 넣었어요. 아래 블록을 Secrets에 붙여 넣으세요.")
        else:
            st.error(msg)
        if ok:
            plain = (new_pw or "").strip()
            st.warning(
                "새 비밀번호는 **지금 한 번만** 표시됩니다. 복사해 구매자에게 안전하게 전달하세요. "
                "공개 채팅·깃에는 넣지 마세요."
            )
            st.code(plain, language=None)
            block = secrets_toml_for_new_buyer(
                new_id.strip(), note=new_note or "", use_placeholder=True
            )
            st.markdown("**Cloud Secrets에 추가할 블록** (비밀번호는 직접 채워 넣기)")
            st.code(block, language="toml")
            ss["_last_secrets_snippet"] = block

    st.divider()
    st.subheader("구매자 목록")
    st.caption("표시: 아이디 · 사용 여부 · 메모만 (비밀번호·해시 비표시)")

    rows = list_buyers_rows()
    if not rows:
        st.caption("아직 구매자 계정이 없어요.")
    else:
        for row in rows:
            u = row["username"]
            enabled = row["enabled"]
            note = row["note"] or ""
            with st.expander(
                f"{'✅' if enabled else '⛔'} {u}"
                + (f" · {note}" if note else ""),
                expanded=False,
            ):
                st.write(f"**아이디:** `{u}`")
                st.write(f"**사용:** {'사용 중' if enabled else '중지'}")
                st.write(f"**메모:** {note or '(없음)'}")
                note_in = st.text_input("메모 수정", value=note, key=f"note_{u}")
                if st.button("메모 저장", key=f"save_note_{u}"):
                    ok, msg = update_buyer_note(u, note_in)
                    (st.success if ok else st.error)(msg)
                    if ok:
                        st.rerun()
                cols = st.columns(3)
                with cols[0]:
                    if enabled:
                        if st.button(
                            "사용 중지", key=f"dis_{u}", use_container_width=True
                        ):
                            ok, msg = set_buyer_enabled(u, False)
                            (st.success if ok else st.error)(msg)
                            if ok:
                                st.rerun()
                    else:
                        if st.button(
                            "다시 사용", key=f"en_{u}", use_container_width=True
                        ):
                            ok, msg = set_buyer_enabled(u, True)
                            (st.success if ok else st.error)(msg)
                            if ok:
                                st.rerun()
                with cols[1]:
                    npw = st.text_input(
                        "새 비밀번호", type="password", key=f"npw_{u}"
                    )
                with cols[2]:
                    if st.button(
                        "비밀번호 변경", key=f"rpw_{u}", use_container_width=True
                    ):
                        plain = (npw or "").strip()
                        ok, msg = reset_buyer_password(u, plain)
                        if ok:
                            st.success(msg)
                            st.warning(
                                "새 비밀번호는 **지금 한 번만** 표시됩니다. "
                                "복사해 저장·전달하세요. 공개 채팅에 넣지 마세요."
                            )
                            st.code(plain, language=None)
                            if f"npw_{u}" in ss:
                                del ss[f"npw_{u}"]
                        else:
                            st.error(msg)

    st.divider()
    st.subheader("Secrets 붙여넣기 (Cloud용)")
    st.caption(
        "Streamlit Cloud → App settings → Secrets 에 붙여 넣으세요. "
        "아래 블록은 **플레이스홀더만** 포함합니다 (실비밀번호·실토큰 없음). "
        "`ADMIN_USERNAME` / `ADMIN_PASSWORD` 는 구매자에게 알리지 마세요. "
        "`data/buyers.json` 은 깃에 올리지 마세요."
    )
    st.code(secrets_toml_block(include_admin_placeholder=True), language="toml")

    st.divider()
    st.caption(
        "구매자 화면(메인)에는 관리자 링크를 넣지 않았습니다. "
        f"{ADMIN_PAGE_HINT} 에서 로그인하세요."
    )

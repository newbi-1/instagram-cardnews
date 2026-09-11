"""관리자 전용 (사이드바 숨김 · 비밀 gate + 이메일 OTP). 구매자 화면에는 링크 없음."""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from src.auth import (
    admin_email_configured,
    admin_gate_configured,
    admin_password_configured,
    create_buyer,
    file_persistence_available,
    get_admin_email,
    list_buyers_rows,
    reset_buyer_password,
    secrets_toml_block,
    secrets_toml_for_new_buyer,
    set_buyer_enabled,
    update_buyer_note,
    verify_admin_gate,
    verify_admin_password,
)
from src.email_otp import (
    can_send_email,
    clear_otp_session,
    email_dev_mode,
    otp_target_hint,
    request_admin_otp,
    verify_otp_code,
)

load_dotenv()

st.set_page_config(page_title="페이지", page_icon="📄", layout="centered")

ss = st.session_state
ss.setdefault("admin_ok", False)
ss.setdefault("admin_flash", "")


def _query_gate() -> str:
    """Read ?gate= from Streamlit query params (string or list)."""
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


def _show_not_found() -> None:
    """Generic denial — do not hint that admin or auth exists."""
    st.title("페이지 없음")
    st.write("요청하신 페이지를 찾을 수 없습니다.")
    st.caption("Access denied")
    st.stop()


# --- Layer 1: secret URL gate ---
gate_ok = admin_gate_configured() and verify_admin_gate(_query_gate())
if not gate_ok:
    _show_not_found()

st.title("🔐 관리자")
st.caption(
    "판매자 전용 · gate URL + 이메일 인증 · "
    "구매자에게 gate·이메일·비밀번호를 공유하지 마세요."
)

with st.expander("판매자: 관리자 여는 방법", expanded=not ss.admin_ok):
    st.markdown(
        """
**구매자 URL** (공유 OK): `https://YOURAPP.streamlit.app/`

**관리자 URL** (비밀 · `ADMIN_GATE` 필수):

```text
https://YOURAPP.streamlit.app/?gate=너의비밀값
```

연 뒤 **Admin** / `/_admin` 페이지로 이동하거나, 페이지 URL에 gate를 붙이세요:

```text
https://YOURAPP.streamlit.app/_admin?gate=너의비밀값
```

Secrets 필수:
- `ADMIN_GATE` — 긴 랜덤 문자열
- `ADMIN_EMAIL` — 판매자 수신 전용 (OTP는 이 주소로만 발송)
- `RESEND_API_KEY` — [Resend](https://resend.com) 무료 API 키 (권장)
- (선택) `ADMIN_PASSWORD` — `ADMIN_EMAIL` 미설정 시에만 비밀번호 백업
- (로컬만) `EMAIL_DEV_MODE=1` — 키 없이 OTP를 화면에 표시 (Cloud 금지)
"""
    )
    if ss.admin_flash:
        st.info(ss.admin_flash)

# --- Layer 2: email OTP (primary) or password backup ---
if not ss.admin_ok:
    use_email = admin_email_configured()
    use_password_backup = (not use_email) and admin_password_configured()

    if not use_email and not use_password_backup:
        st.error(
            "인증 수단이 없어요. Secrets에 `ADMIN_EMAIL` + `RESEND_API_KEY` "
            "(권장) 또는 백업용 `ADMIN_PASSWORD` 를 넣어 주세요."
        )
        st.code(
            'ADMIN_GATE = "긴_랜덤_비밀값"\n'
            'ADMIN_EMAIL = "seller@example.com"\n'
            'RESEND_API_KEY = "re_..."\n'
            '# ADMIN_PASSWORD = "백업용_선택"\n'
            '# EMAIL_DEV_MODE = "1"  # 로컬만',
            language="toml",
        )
        st.stop()

    if use_email:
        st.subheader("이메일 인증")
        st.caption(f"등록된 관리자 메일로 인증번호를 보냅니다 · {otp_target_hint()}")

        if not can_send_email() and not email_dev_mode():
            st.warning(
                "RESEND_API_KEY 가 없습니다. "
                "https://resend.com 에서 무료 키를 발급해 Secrets에 넣으세요. "
                "로컬 테스트만 `EMAIL_DEV_MODE=1` 로 UI에 인증번호를 표시할 수 있습니다."
            )

        if st.button("인증번호 보내기", type="primary", use_container_width=True):
            ok, msg, dev_code = request_admin_otp(ss)
            if ok:
                st.success(msg)
                if dev_code and email_dev_mode():
                    st.error(
                        "⚠️ EMAIL_DEV_MODE — 아래 코드는 테스트용입니다. "
                        "Cloud/운영에서는 절대 EMAIL_DEV_MODE 를 켜지 마세요."
                    )
                    st.code(dev_code, language=None)
                    ss.admin_flash = f"DEV OTP 표시됨 (로컬만). 대상: {otp_target_hint()}"
            else:
                st.error(msg)

        code_in = st.text_input(
            "인증번호 6자리",
            max_chars=6,
            key="admin_otp_in",
            placeholder="000000",
        )
        if st.button("인증하고 입장", use_container_width=True):
            ok, msg = verify_otp_code(ss, code_in or "")
            if ok:
                ss.admin_ok = True
                ss.admin_flash = (
                    "이메일 인증 완료. 북마크는 gate 포함 URL만: "
                    "https://YOURAPP.streamlit.app/_admin?gate=너의비밀값"
                )
                st.rerun()
            else:
                st.error(msg)

        if email_dev_mode() and ss.get("admin_otp_dev_code"):
            st.warning("DEV MODE: 세션에 저장된 테스트 OTP가 있습니다 (새로고침 시 위 버튼으로 재발급).")

    else:
        # Backup: password only when ADMIN_EMAIL is not configured
        st.subheader("비밀번호 입장 (백업)")
        st.caption("`ADMIN_EMAIL` 이 없어 비밀번호 백업 모드입니다. 가능하면 이메일 OTP를 설정하세요.")
        pw = st.text_input("관리자 비밀번호", type="password", key="admin_pw_in")
        if st.button("입장", type="primary", use_container_width=True):
            if verify_admin_password(pw or ""):
                ss.admin_ok = True
                ss.admin_flash = "비밀번호 백업 입장. ADMIN_EMAIL + Resend OTP 설정을 권장합니다."
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않아요.")

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
        plain = (new_pw or "").strip()
        st.warning(
            "새 비밀번호는 **지금 한 번만** 표시됩니다. 복사해 구매자에게 안전하게 전달하세요. "
            "공개 채팅·깃에는 넣지 마세요."
        )
        st.code(plain, language=None)
        # Secrets paste uses placeholders — never live password from session
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
        # List: id / enabled / note only — never password or hash
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
    "`ADMIN_GATE` / `ADMIN_EMAIL` / `RESEND_API_KEY` 는 구매자에게 알리지 마세요. "
    "`data/buyers.json` 은 깃에 올리지 마세요."
)
st.code(secrets_toml_block(include_admin_placeholder=True), language="toml")

st.divider()
st.caption(
    "구매자 화면(메인)에는 관리자 링크를 넣지 않았습니다. "
    "gate가 포함된 URL만 판매자가 보관하세요."
)

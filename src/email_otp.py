"""Admin email OTP — send ONLY to configured ADMIN_EMAIL (Resend or local dev mode)."""

from __future__ import annotations

import hashlib
import os
import secrets as pysecrets
import time
from typing import Any

import requests

from src.auth import _secret_str, get_admin_email

OTP_TTL_SEC = 10 * 60
OTP_LENGTH = 6
RESEND_API = "https://api.resend.com/emails"


def _secret_or_env(*keys: str) -> str:
    return _secret_str(*keys)


def email_dev_mode() -> bool:
    """Local testing only. Never enable on Streamlit Cloud production."""
    raw = (_secret_or_env("EMAIL_DEV_MODE") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def get_resend_api_key() -> str:
    return _secret_or_env("RESEND_API_KEY")


def get_mail_from() -> str:
    """Resend verified from-address; default onboarding sender for free tier tests."""
    return _secret_or_env("RESEND_FROM", "MAIL_FROM") or "onboarding@resend.dev"


def can_send_email() -> bool:
    return bool(get_resend_api_key())


def generate_otp_code(length: int = OTP_LENGTH) -> str:
    # numeric, avoid leading-zero loss by keeping as zero-padded string
    n = pysecrets.randbelow(10**length)
    return str(n).zfill(length)


def hash_otp(code: str, salt: str) -> str:
    digest = hashlib.sha256(f"{salt}:{code}".encode("utf-8")).hexdigest()
    return digest


def store_otp_in_session(ss: Any, code: str) -> None:
    salt = pysecrets.token_hex(8)
    ss["admin_otp_salt"] = salt
    ss["admin_otp_hash"] = hash_otp(code, salt)
    ss["admin_otp_expires"] = time.time() + OTP_TTL_SEC
    ss["admin_otp_sent_at"] = time.time()
    ss["admin_otp_attempts"] = 0


def clear_otp_session(ss: Any) -> None:
    for k in (
        "admin_otp_salt",
        "admin_otp_hash",
        "admin_otp_expires",
        "admin_otp_sent_at",
        "admin_otp_attempts",
        "admin_otp_dev_code",
    ):
        if k in ss:
            del ss[k]


def verify_otp_code(ss: Any, code: str) -> tuple[bool, str]:
    expected_hash = ss.get("admin_otp_hash") or ""
    salt = ss.get("admin_otp_salt") or ""
    expires = float(ss.get("admin_otp_expires") or 0)
    if not expected_hash or not salt:
        return False, "인증번호를 먼저 보내 주세요."
    if time.time() > expires:
        clear_otp_session(ss)
        return False, "인증번호가 만료됐어요. 다시 보내 주세요."
    attempts = int(ss.get("admin_otp_attempts") or 0)
    if attempts >= 5:
        clear_otp_session(ss)
        return False, "시도 횟수를 초과했어요. 인증번호를 다시 보내 주세요."
    ss["admin_otp_attempts"] = attempts + 1
    got = (code or "").strip().replace(" ", "")
    if not got or len(got) != OTP_LENGTH or not got.isdigit():
        return False, "인증번호 6자리를 입력해 주세요."
    check = hash_otp(got, salt)
    if not pysecrets.compare_digest(check, expected_hash):
        return False, "인증번호가 올바르지 않아요."
    clear_otp_session(ss)
    return True, ""


def send_otp_via_resend(to_email: str, code: str) -> tuple[bool, str]:
    api_key = get_resend_api_key()
    if not api_key:
        return False, "RESEND_API_KEY 가 없어요."
    from_addr = get_mail_from()
    payload = {
        "from": from_addr,
        "to": [to_email],
        "subject": "[카드뉴스] 관리자 인증번호",
        "text": (
            f"관리자 인증번호: {code}\n\n"
            f"{OTP_TTL_SEC // 60}분 안에 입력해 주세요.\n"
            "본인이 요청하지 않았다면 이 메일을 무시하세요."
        ),
    }
    try:
        r = requests.post(
            RESEND_API,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
    except requests.RequestException as exc:
        return False, f"메일 전송 실패: {exc}"
    if r.status_code >= 400:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        return False, f"Resend 오류 ({r.status_code}): {detail}"
    return True, "인증번호를 등록된 판매자 이메일로 보냈어요."


def request_admin_otp(ss: Any) -> tuple[bool, str, str | None]:
    """
    Generate OTP and deliver ONLY to ADMIN_EMAIL.
    Returns (ok, message, dev_code_or_none).
    dev_code is set only when EMAIL_DEV_MODE=1 and no Resend key path used for display.
    """
    to_email = get_admin_email()
    if not to_email:
        return False, "ADMIN_EMAIL 이 Secrets/환경변수에 없어요.", None

    # throttle resend
    last = float(ss.get("admin_otp_sent_at") or 0)
    if last and (time.time() - last) < 30:
        return False, "잠시 후 다시 보내 주세요 (30초).", None

    code = generate_otp_code()
    store_otp_in_session(ss, code)

    if can_send_email():
        ok, msg = send_otp_via_resend(to_email, code)
        if not ok:
            # keep stored OTP so retry of send can regenerate; clear on hard fail
            clear_otp_session(ss)
            return False, msg, None
        # never return code when real email sent
        if "admin_otp_dev_code" in ss:
            del ss["admin_otp_dev_code"]
        return True, msg, None

    if email_dev_mode():
        ss["admin_otp_dev_code"] = code
        masked = _mask_email(to_email)
        return (
            True,
            (
                f"EMAIL_DEV_MODE=1 · 메일은 안 보내고 UI에만 표시합니다. "
                f"수신함(설정): {masked}. Cloud 운영에서는 RESEND_API_KEY 를 넣으세요."
            ),
            code,
        )

    clear_otp_session(ss)
    return (
        False,
        (
            "메일 전송 키가 없어요. Secrets에 RESEND_API_KEY 를 넣거나, "
            "로컬 테스트만 EMAIL_DEV_MODE=1 을 사용하세요. "
            "(https://resend.com 무료 키)"
        ),
        None,
    )


def _mask_email(email: str) -> str:
    email = (email or "").strip()
    if "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        shown = local[:1] + "*"
    else:
        shown = local[:2] + "***"
    return f"{shown}@{domain}"


def otp_target_hint() -> str:
    """Masked ADMIN_EMAIL for UI — never ask user for an address."""
    return _mask_email(get_admin_email())

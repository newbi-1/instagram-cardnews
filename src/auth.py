"""Buyer accounts + admin password — local JSON and/or Streamlit secrets."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets as pysecrets
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BUYERS_PATH = ROOT / "data" / "buyers.json"

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{2,40}$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_username(username: str) -> str | None:
    u = (username or "").strip()
    if not u:
        return "아이디를 입력해 주세요."
    if not _USERNAME_RE.match(u):
        return "아이디는 영문·숫자·._- 만, 2~40자예요."
    return None


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or pysecrets.token_hex(8)
    digest = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
    return f"sha256${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    stored = (stored or "").strip()
    if not stored:
        return False
    if stored.startswith("sha256$"):
        try:
            _, salt, digest = stored.split("$", 2)
        except ValueError:
            return False
        check = hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()
        return pysecrets.compare_digest(check, digest)
    # Plain fallback (secrets.toml convenience) — constant-time-ish compare
    return pysecrets.compare_digest(stored, password)


def _empty_store() -> dict[str, Any]:
    return {"version": 1, "buyers": {}}


def file_persistence_available() -> bool:
    """True if we can create/update data/buyers.json (local / writable disk)."""
    try:
        BUYERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        if BUYERS_PATH.exists():
            with BUYERS_PATH.open("a", encoding="utf-8"):
                pass
            return True
        probe = BUYERS_PATH.parent / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def load_buyers_file() -> dict[str, Any]:
    if not BUYERS_PATH.exists():
        return _empty_store()
    try:
        data = json.loads(BUYERS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_store()
    if not isinstance(data, dict):
        return _empty_store()
    buyers = data.get("buyers")
    if not isinstance(buyers, dict):
        data["buyers"] = {}
    return data


def save_buyers_file(store: dict[str, Any]) -> tuple[bool, str]:
    try:
        BUYERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = BUYERS_PATH.with_suffix(".tmp")
        payload = json.dumps(store, ensure_ascii=False, indent=2)
        tmp.write_text(payload + "\n", encoding="utf-8")
        tmp.replace(BUYERS_PATH)
        return True, str(BUYERS_PATH)
    except OSError as exc:
        return False, str(exc)


def _secrets_obj() -> Any | None:
    try:
        import streamlit as st

        return st.secrets
    except Exception:
        return None


def get_admin_password() -> str:
    env = (os.environ.get("ADMIN_PASSWORD") or "").strip()
    if env:
        return env
    sec = _secrets_obj()
    if sec is None:
        return ""
    try:
        if "ADMIN_PASSWORD" in sec and sec["ADMIN_PASSWORD"]:
            return str(sec["ADMIN_PASSWORD"]).strip()
    except Exception:
        pass
    return ""


def admin_password_configured() -> bool:
    return bool(get_admin_password())


def verify_admin_password(password: str) -> bool:
    expected = get_admin_password()
    if not expected:
        return False
    return pysecrets.compare_digest((password or "").strip(), expected)


def _parse_secrets_buyers() -> dict[str, dict[str, Any]]:
    """Read [buyers.<id>] tables from st.secrets / nested dict."""
    out: dict[str, dict[str, Any]] = {}
    sec = _secrets_obj()
    if sec is None:
        return out
    try:
        raw = sec.get("buyers", None) if hasattr(sec, "get") else None
        if raw is None:
            try:
                raw = sec["buyers"]
            except Exception:
                return out
    except Exception:
        return out

    # Mapping of username -> {password, note, enabled}
    try:
        items = dict(raw)
    except Exception:
        return out

    for username, meta in items.items():
        u = str(username).strip()
        if not u:
            continue
        if isinstance(meta, str):
            # buyers.user = "password"
            out[u] = {
                "password": meta,
                "password_hash": "",
                "note": "",
                "enabled": True,
                "source": "secrets",
            }
            continue
        try:
            m = dict(meta)
        except Exception:
            continue
        enabled = m.get("enabled", True)
        if isinstance(enabled, str):
            enabled = enabled.strip().lower() not in {"0", "false", "no", "off"}
        out[u] = {
            "password": str(m.get("password") or "").strip(),
            "password_hash": str(m.get("password_hash") or "").strip(),
            "note": str(m.get("note") or "").strip(),
            "enabled": bool(enabled),
            "source": "secrets",
        }
    return out


def merged_buyers() -> dict[str, dict[str, Any]]:
    """
    File buyers + secrets buyers.
    Secrets win on conflict (Cloud source of truth when pasted).
    """
    merged: dict[str, dict[str, Any]] = {}
    store = load_buyers_file()
    for u, meta in (store.get("buyers") or {}).items():
        if not isinstance(meta, dict):
            continue
        merged[str(u)] = {
            "password_hash": str(meta.get("password_hash") or ""),
            "password": "",
            "note": str(meta.get("note") or ""),
            "enabled": bool(meta.get("enabled", True)),
            "created_at": str(meta.get("created_at") or ""),
            "source": "file",
        }
    for u, meta in _parse_secrets_buyers().items():
        base = merged.get(u, {})
        base.update(meta)
        base["source"] = "secrets" if meta.get("source") == "secrets" else base.get("source", "secrets")
        merged[u] = base
    return merged


def authenticate_buyer(username: str, password: str) -> tuple[bool, str]:
    u = (username or "").strip()
    if not u or not password:
        return False, "아이디와 비밀번호를 입력해 주세요."
    buyers = merged_buyers()
    meta = buyers.get(u)
    if not meta:
        return False, "아이디 또는 비밀번호가 올바르지 않아요."
    if not meta.get("enabled", True):
        return False, "이 계정은 사용 중지됐어요. 판매자에게 문의해 주세요."
    stored_hash = (meta.get("password_hash") or "").strip()
    stored_plain = (meta.get("password") or "").strip()
    ok = False
    if stored_hash:
        ok = verify_password(password, stored_hash)
    if not ok and stored_plain:
        ok = verify_password(password, stored_plain)
    if not ok:
        return False, "아이디 또는 비밀번호가 올바르지 않아요."
    return True, ""


def create_buyer(
    username: str,
    password: str,
    note: str = "",
    *,
    persist: bool = True,
) -> tuple[bool, str, dict[str, Any] | None]:
    err = validate_username(username)
    if err:
        return False, err, None
    if not (password or "").strip() or len(password.strip()) < 4:
        return False, "비밀번호는 4자 이상이어야 해요.", None
    u = username.strip()
    store = load_buyers_file()
    buyers = store.setdefault("buyers", {})
    secrets_hit = u in _parse_secrets_buyers()
    if u in buyers:
        return False, "이미 파일에 있는 아이디예요.", None
    if secrets_hit and not persist:
        pass
    record = {
        "password_hash": hash_password(password.strip()),
        "note": (note or "").strip(),
        "enabled": True,
        "created_at": _utc_now(),
    }
    if not persist:
        return True, "메모리만 (파일 저장 안 함)", record
    buyers[u] = record
    ok, msg = save_buyers_file(store)
    if not ok:
        return False, f"저장 실패: {msg}", record
    return True, "저장했어요.", record


def set_buyer_enabled(username: str, enabled: bool) -> tuple[bool, str]:
    u = (username or "").strip()
    store = load_buyers_file()
    buyers = store.get("buyers") or {}
    if u not in buyers:
        if u in _parse_secrets_buyers():
            return False, "Secrets에만 있는 계정은 여기서 끄려면 secrets.toml에서 enabled=false 로 바꿔 주세요."
        return False, "파일에 없는 아이디예요."
    buyers[u]["enabled"] = bool(enabled)
    ok, msg = save_buyers_file(store)
    return (ok, "저장했어요." if ok else f"저장 실패: {msg}")


def update_buyer_note(username: str, note: str) -> tuple[bool, str]:
    u = (username or "").strip()
    store = load_buyers_file()
    buyers = store.get("buyers") or {}
    if u not in buyers:
        return False, "파일에 없는 아이디예요."
    buyers[u]["note"] = (note or "").strip()
    ok, msg = save_buyers_file(store)
    return (ok, "저장했어요." if ok else f"저장 실패: {msg}")


def reset_buyer_password(username: str, new_password: str) -> tuple[bool, str]:
    u = (username or "").strip()
    if len((new_password or "").strip()) < 4:
        return False, "비밀번호는 4자 이상이어야 해요."
    store = load_buyers_file()
    buyers = store.get("buyers") or {}
    if u not in buyers:
        return False, "파일에 없는 아이디예요."
    buyers[u]["password_hash"] = hash_password(new_password.strip())
    ok, msg = save_buyers_file(store)
    return (ok, "비밀번호를 바꿨어요." if ok else f"저장 실패: {msg}")


def secrets_toml_block(include_admin_placeholder: bool = True) -> str:
    """Copy-paste block for Streamlit Cloud secrets (plain passwords)."""
    lines: list[str] = []
    if include_admin_placeholder:
        admin = get_admin_password() or "여기에_관리자_비밀번호"
        lines.append(f'ADMIN_PASSWORD = "{admin}"')
        lines.append("")
    # Prefer file records + merged view with plain pwd only when we just created
    store = load_buyers_file()
    file_buyers = store.get("buyers") or {}
    if not file_buyers:
        lines.append("# [buyers.아이디]")
        lines.append('# password = "구매자비밀번호"')
        lines.append('# note = "메모"')
        lines.append("enabled = true")
        return "\n".join(lines) + "\n"

    for u, meta in sorted(file_buyers.items()):
        lines.append(f"[buyers.{u}]")
        # Cloud secrets usually use plain password — seller sets when pasting
        lines.append('password = "여기에_구매자_비밀번호"')
        note = str(meta.get("note") or "").replace('"', '\\"')
        lines.append(f'note = "{note}"')
        enabled = "true" if meta.get("enabled", True) else "false"
        lines.append(f"enabled = {enabled}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def secrets_toml_for_new_buyer(username: str, password: str, note: str = "", enabled: bool = True) -> str:
    u = username.strip()
    note_esc = (note or "").replace('"', '\\"')
    en = "true" if enabled else "false"
    return (
        f"[buyers.{u}]\n"
        f'password = "{password}"\n'
        f'note = "{note_esc}"\n'
        f"enabled = {en}\n"
    )


def list_buyers_rows() -> list[dict[str, Any]]:
    rows = []
    for u, meta in sorted(merged_buyers().items()):
        rows.append(
            {
                "username": u,
                "note": meta.get("note") or "",
                "enabled": bool(meta.get("enabled", True)),
                "source": meta.get("source") or "",
                "created_at": meta.get("created_at") or "",
            }
        )
    return rows

"""Per-buyer daily publish quota (calendar day Asia/Seoul)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from .auth import load_buyers_file, save_buyers_file

SEOUL = ZoneInfo("Asia/Seoul")
DEFAULT_DAILY_LIMIT = 3
OVER_LIMIT_MSG = "추가 발행은 관리자에게 문의하세요"


def seoul_today() -> str:
    """YYYY-MM-DD in Asia/Seoul."""
    return datetime.now(SEOUL).strftime("%Y-%m-%d")


def _buyer_slot(store: dict[str, Any], username: str) -> dict[str, Any] | None:
    u = (username or "").strip()
    buyers = store.get("buyers") or {}
    meta = buyers.get(u)
    if not isinstance(meta, dict):
        return None
    return meta


def get_daily_limit(username: str, default: int = DEFAULT_DAILY_LIMIT) -> int:
    store = load_buyers_file()
    meta = _buyer_slot(store, username)
    if not meta:
        return default
    try:
        lim = int(meta.get("daily_publish_limit", default))
    except (TypeError, ValueError):
        lim = default
    return max(0, lim)


def set_daily_limit(username: str, limit: int) -> tuple[bool, str]:
    u = (username or "").strip()
    store = load_buyers_file()
    buyers = store.setdefault("buyers", {})
    try:
        lim = int(limit)
    except (TypeError, ValueError):
        return False, "숫자로 입력해 주세요."
    if lim < 0:
        return False, "0 이상이어야 해요."
    if u not in buyers:
        # Secrets-only account: create lightweight file stub for quota/limit
        buyers[u] = {
            "password_hash": "",
            "note": "(한도 설정용 stub — 로그인은 Secrets)",
            "enabled": True,
            "created_at": "",
            "daily_publish_limit": lim,
            "quota": {"date": seoul_today(), "count": 0},
        }
    else:
        buyers[u]["daily_publish_limit"] = lim
        if "quota" not in buyers[u]:
            buyers[u]["quota"] = {"date": seoul_today(), "count": 0}
    ok, msg = save_buyers_file(store)
    return (ok, "저장했어요." if ok else f"저장 실패: {msg}")


def get_usage(username: str) -> tuple[str, int]:
    """Return (date_seoul, count_today). Resets conceptually when date differs."""
    store = load_buyers_file()
    meta = _buyer_slot(store, username)
    today = seoul_today()
    if not meta:
        return today, 0
    quota = meta.get("quota") or {}
    if not isinstance(quota, dict):
        return today, 0
    qdate = str(quota.get("date") or "")
    try:
        count = int(quota.get("count") or 0)
    except (TypeError, ValueError):
        count = 0
    if qdate != today:
        return today, 0
    return today, max(0, count)


def remaining_today(username: str) -> int:
    lim = get_daily_limit(username)
    _, used = get_usage(username)
    return max(0, lim - used)


def can_publish(username: str) -> tuple[bool, str]:
    """True if under daily limit. Message for UI when blocked."""
    rem = remaining_today(username)
    if rem <= 0:
        return False, OVER_LIMIT_MSG
    return True, ""


def record_publish(username: str) -> tuple[bool, str]:
    """Increment today's publish count (call only after successful real post)."""
    u = (username or "").strip()
    store = load_buyers_file()
    buyers = store.setdefault("buyers", {})
    if u not in buyers:
        # Secrets-only buyer: create a lightweight quota stub without password
        buyers[u] = {
            "password_hash": "",
            "note": "(quota stub — secrets account)",
            "enabled": True,
            "daily_publish_limit": DEFAULT_DAILY_LIMIT,
            "created_at": "",
        }
    today = seoul_today()
    meta = buyers[u]
    quota = meta.get("quota") if isinstance(meta.get("quota"), dict) else {}
    qdate = str(quota.get("date") or "")
    try:
        count = int(quota.get("count") or 0)
    except (TypeError, ValueError):
        count = 0
    if qdate != today:
        count = 0
    count += 1
    meta["quota"] = {"date": today, "count": count}
    if "daily_publish_limit" not in meta:
        meta["daily_publish_limit"] = DEFAULT_DAILY_LIMIT
    ok, msg = save_buyers_file(store)
    return (ok, "기록했어요." if ok else f"저장 실패: {msg}")


def ensure_buyer_quota_fields(record: dict[str, Any]) -> dict[str, Any]:
    """Mutate/return buyer record with default quota fields."""
    if "daily_publish_limit" not in record:
        record["daily_publish_limit"] = DEFAULT_DAILY_LIMIT
    if "quota" not in record or not isinstance(record.get("quota"), dict):
        record["quota"] = {"date": seoul_today(), "count": 0}
    return record


def usage_summary_for_admin(username: str) -> dict[str, Any]:
    lim = get_daily_limit(username)
    date, used = get_usage(username)
    return {
        "date": date,
        "used": used,
        "limit": lim,
        "remaining": max(0, lim - used),
    }

"""Per-buyer topics, caption templates, and scheduled publish jobs."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")
ROOT = Path(__file__).resolve().parent.parent
SETTINGS_PATH = ROOT / "data" / "buyer_settings.json"
SCHEDULES_PATH = ROOT / "data" / "schedules.json"

MAX_TOPICS = 5
MAX_CAPTION_TEMPLATES = 5

DEFAULT_CAPTION = "[{topic}] 오늘의 카드뉴스\n\n#카드뉴스 #{topic}"


def _empty_settings_store() -> dict[str, Any]:
    return {"version": 1, "settings": {}}


def _empty_schedules_store() -> dict[str, Any]:
    return {"version": 1, "jobs": []}


def _default_buyer_settings() -> dict[str, Any]:
    return {
        "topics": [
            {"text": "", "enabled": False},
            {"text": "", "enabled": False},
            {"text": "", "enabled": False},
            {"text": "", "enabled": False},
            {"text": "", "enabled": False},
        ],
        "caption_templates": [
            {
                "text": DEFAULT_CAPTION,
                "mode": "manual",  # manual | ai
                "enabled": True,
            },
            {"text": "", "mode": "ai", "enabled": False},
            {"text": "", "mode": "ai", "enabled": False},
            {"text": "", "mode": "ai", "enabled": False},
            {"text": "", "mode": "ai", "enabled": False},
        ],
        "closing_greeting": "오늘도 응원해요 💛 저장해 두고 다시 보세요.",
        "always_include": "",
    }


def _load_json(path: Path, empty: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return empty
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty
    if not isinstance(data, dict):
        return empty
    return data


def _save_json(path: Path, data: dict[str, Any]) -> tuple[bool, str]:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        tmp.write_text(payload + "\n", encoding="utf-8")
        tmp.replace(path)
        return True, str(path)
    except OSError as exc:
        return False, str(exc)


def load_settings_store() -> dict[str, Any]:
    data = _load_json(SETTINGS_PATH, _empty_settings_store())
    if "settings" not in data or not isinstance(data["settings"], dict):
        data["settings"] = {}
    return data


def save_settings_store(store: dict[str, Any]) -> tuple[bool, str]:
    return _save_json(SETTINGS_PATH, store)


def get_buyer_settings(username: str) -> dict[str, Any]:
    u = (username or "").strip()
    store = load_settings_store()
    raw = store.get("settings", {}).get(u)
    base = _default_buyer_settings()
    if not isinstance(raw, dict):
        return base
    # Merge with defaults (pad to 5 slots)
    topics = list(raw.get("topics") or [])
    caps = list(raw.get("caption_templates") or [])
    out = _default_buyer_settings()
    merged_topics = []
    for i in range(MAX_TOPICS):
        if i < len(topics) and isinstance(topics[i], dict):
            merged_topics.append(
                {
                    "text": str(topics[i].get("text") or ""),
                    "enabled": bool(topics[i].get("enabled", False)),
                }
            )
        else:
            merged_topics.append(out["topics"][i])
    merged_caps = []
    for i in range(MAX_CAPTION_TEMPLATES):
        if i < len(caps) and isinstance(caps[i], dict):
            mode = str(caps[i].get("mode") or "manual").lower()
            if mode not in ("manual", "ai"):
                mode = "manual"
            merged_caps.append(
                {
                    "text": str(caps[i].get("text") or ""),
                    "mode": mode,
                    "enabled": bool(caps[i].get("enabled", False)),
                }
            )
        else:
            merged_caps.append(out["caption_templates"][i])
    out["topics"] = merged_topics
    out["caption_templates"] = merged_caps
    if "closing_greeting" in raw:
        out["closing_greeting"] = str(raw.get("closing_greeting") or "")
    if "always_include" in raw:
        out["always_include"] = str(raw.get("always_include") or "")
    return out


def save_buyer_settings(username: str, settings: dict[str, Any]) -> tuple[bool, str]:
    u = (username or "").strip()
    if not u:
        return False, "로그인 필요"
    store = load_settings_store()
    # Normalize
    topics = []
    for t in (settings.get("topics") or [])[:MAX_TOPICS]:
        if not isinstance(t, dict):
            continue
        topics.append(
            {
                "text": str(t.get("text") or "").strip(),
                "enabled": bool(t.get("enabled", False)),
            }
        )
    while len(topics) < MAX_TOPICS:
        topics.append({"text": "", "enabled": False})

    caps = []
    for c in (settings.get("caption_templates") or [])[:MAX_CAPTION_TEMPLATES]:
        if not isinstance(c, dict):
            continue
        mode = str(c.get("mode") or "manual").lower()
        if mode not in ("manual", "ai"):
            mode = "manual"
        caps.append(
            {
                "text": str(c.get("text") or ""),
                "mode": mode,
                "enabled": bool(c.get("enabled", False)),
            }
        )
    while len(caps) < MAX_CAPTION_TEMPLATES:
        caps.append({"text": "", "mode": "ai", "enabled": False})

    store.setdefault("settings", {})[u] = {
        "topics": topics,
        "caption_templates": caps,
        "closing_greeting": str(settings.get("closing_greeting") or ""),
        "always_include": str(settings.get("always_include") or ""),
    }
    return save_settings_store(store)


def enabled_topics(username: str) -> list[str]:
    """Non-empty topic texts that are toggled on."""
    s = get_buyer_settings(username)
    out: list[str] = []
    for t in s.get("topics") or []:
        text = str(t.get("text") or "").strip()
        if text and t.get("enabled"):
            out.append(text)
    return out


def enabled_caption_templates(username: str) -> list[dict[str, Any]]:
    s = get_buyer_settings(username)
    out: list[dict[str, Any]] = []
    for i, c in enumerate(s.get("caption_templates") or []):
        if not c.get("enabled"):
            continue
        # AI mode needs no text; manual needs text
        mode = c.get("mode") or "manual"
        text = str(c.get("text") or "").strip()
        if mode == "manual" and not text:
            continue
        out.append({"index": i, "text": text, "mode": mode})
    return out


def apply_placeholders(template: str, *, topic: str = "", **extra: str) -> str:
    raw = template or ""
    out = (
        raw.replace("{주제}", topic)
        .replace("{topic}", topic)
        .replace("{TOPIC}", topic)
    )
    for k, v in extra.items():
        out = out.replace("{" + k + "}", v)
    return out


def draft_ai_caption(topic: str, headlines: list[str] | None = None) -> str:
    """Free heuristic Instagram caption from topic + news headlines (no paid API)."""
    topic = (topic or "").strip() or "오늘 소식"
    heads = [h.strip() for h in (headlines or []) if h and str(h).strip()]
    lines: list[str] = []
    lines.append(f"📌 {topic}")
    lines.append("")
    if heads:
        lines.append("오늘 눈에 띄는 이야기")
        for h in heads[:3]:
            short = h if len(h) <= 60 else h[:57] + "…"
            lines.append(f"· {short}")
        lines.append("")
        lines.append("핵심만 카드로 정리해 봤어요. 저장해 두고 필요할 때 다시 보세요 💛")
    else:
        lines.append(f"'{topic}' 관련해서 지금 알아두면 좋은 포인트만 골랐어요.")
        lines.append("저장해 두고 필요할 때 다시 보세요 💛")
    lines.append("")
    # Simple hashtag from topic words
    tag = re.sub(r"[^\w가-힣]+", "", topic.replace(" ", ""))[:20] or "카드뉴스"
    lines.append(f"#카드뉴스 #{tag} #인스타카드뉴스")
    return "\n".join(lines)


def resolve_caption(
    *,
    username: str,
    topic: str,
    headlines: list[str] | None = None,
    template_index: int | None = None,
) -> str:
    """Pick an enabled caption template (or first) and resolve manual/AI."""
    templates = enabled_caption_templates(username)
    chosen: dict[str, Any] | None = None
    if template_index is not None:
        for t in templates:
            if t.get("index") == template_index:
                chosen = t
                break
    if chosen is None and templates:
        chosen = templates[0]
    if chosen is None:
        # Fall back to defaults
        s = get_buyer_settings(username)
        caps = s.get("caption_templates") or []
        if caps:
            chosen = {
                "text": caps[0].get("text") or DEFAULT_CAPTION,
                "mode": caps[0].get("mode") or "manual",
            }
        else:
            return draft_ai_caption(topic, headlines)

    if chosen.get("mode") == "ai":
        return draft_ai_caption(topic, headlines)
    return apply_placeholders(chosen.get("text") or DEFAULT_CAPTION, topic=topic)


# ── Schedules ────────────────────────────────────────────


def load_schedules() -> dict[str, Any]:
    data = _load_json(SCHEDULES_PATH, _empty_schedules_store())
    if "jobs" not in data or not isinstance(data["jobs"], list):
        data["jobs"] = []
    return data


def save_schedules(store: dict[str, Any]) -> tuple[bool, str]:
    return _save_json(SCHEDULES_PATH, store)


def add_schedule_job(
    *,
    username: str,
    run_at_iso: str,
    image_paths: list[str],
    caption: str,
    topic: str = "",
) -> tuple[bool, str, dict[str, Any] | None]:
    """Save a scheduled publish job. run_at_iso should be timezone-aware ISO or Seoul local."""
    u = (username or "").strip()
    if not u:
        return False, "로그인 필요", None
    if not image_paths:
        return False, "이미지 경로가 없어요.", None
    store = load_schedules()
    job = {
        "id": uuid.uuid4().hex[:12],
        "username": u,
        "run_at": run_at_iso,
        "image_paths": [str(p) for p in image_paths],
        "caption": caption or "",
        "topic": topic or "",
        "status": "pending",
        "created_at": datetime.now(SEOUL).isoformat(),
        "result_message": "",
    }
    store.setdefault("jobs", []).append(job)
    ok, msg = save_schedules(store)
    if not ok:
        return False, f"저장 실패: {msg}", None
    return True, "예약했어요.", job


def list_buyer_jobs(username: str, *, include_done: bool = True) -> list[dict[str, Any]]:
    u = (username or "").strip()
    jobs = []
    for j in load_schedules().get("jobs") or []:
        if not isinstance(j, dict):
            continue
        if j.get("username") != u:
            continue
        if not include_done and j.get("status") not in ("pending",):
            continue
        jobs.append(j)
    jobs.sort(key=lambda x: str(x.get("run_at") or ""))
    return jobs


def _parse_run_at(raw: str) -> datetime | None:
    s = (raw or "").strip()
    if not s:
        return None
    try:
        # fromisoformat handles +09:00 and Z (3.11+)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=SEOUL)
        return dt
    except ValueError:
        return None


def due_pending_jobs(now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(SEOUL)
    out = []
    for j in load_schedules().get("jobs") or []:
        if not isinstance(j, dict):
            continue
        if j.get("status") != "pending":
            continue
        dt = _parse_run_at(str(j.get("run_at") or ""))
        if dt is None:
            continue
        if dt <= now:
            out.append(j)
    return out


def update_job_status(
    job_id: str,
    *,
    status: str,
    result_message: str = "",
) -> tuple[bool, str]:
    store = load_schedules()
    found = False
    for j in store.get("jobs") or []:
        if isinstance(j, dict) and j.get("id") == job_id:
            j["status"] = status
            j["result_message"] = result_message
            j["processed_at"] = datetime.now(SEOUL).isoformat()
            found = True
            break
    if not found:
        return False, "잡을 찾지 못했어요."
    return save_schedules(store)

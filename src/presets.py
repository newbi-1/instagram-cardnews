"""주제·타겟·스타일 프리셋 (한국어)."""

from __future__ import annotations

TOPICS = [
    "신메뉴",
    "후기",
    "이벤트",
    "꿀팁",
    "공지",
    "전후",
    "사용법",
    "할인/프로모",
    "혜택가이드",
]

AUDIENCES = [
    "직장맘",
    "자취생",
    "사장님",
    "입문자",
    "학부모",
    "직장인",
    "동네 주민",
    "학생",
]

# style_id -> display name + palette
STYLES = {
    "style.clean": {
        "name": "Navy Guide",
        "bg": (245, 247, 250),
        "card": (255, 255, 255),
        "accent": (15, 40, 80),
        "accent2": (30, 80, 160),
        "text": (20, 30, 50),
        "muted": (90, 100, 120),
        "bar": (15, 40, 80),
    },
    "style.bold": {
        "name": "Violet Checklist",
        "bg": (250, 245, 255),
        "card": (255, 255, 255),
        "accent": (90, 40, 160),
        "accent2": (140, 70, 220),
        "text": (30, 20, 50),
        "muted": (100, 90, 120),
        "bar": (90, 40, 160),
    },
    "style.soft": {
        "name": "Soft Blue Card",
        "bg": (235, 245, 255),
        "card": (255, 255, 255),
        "accent": (70, 130, 200),
        "accent2": (120, 180, 230),
        "text": (40, 55, 75),
        "muted": (100, 120, 140),
        "bar": (70, 130, 200),
    },
}


def style_label(style_id: str) -> str:
    s = STYLES.get(style_id)
    if not s:
        return style_id
    return f"{s['name']} ({style_id})"

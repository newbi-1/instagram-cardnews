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
# Styles differ via overlay tint + accent (photo bg shared look).
STYLES = {
    "style.clean": {
        "name": "Navy Guide",
        "bg": (245, 247, 250),
        "card": (255, 255, 255),
        "accent": (20, 55, 110),
        "accent2": (50, 110, 190),
        "text": (28, 36, 52),
        "muted": (95, 108, 128),
        "bar": (20, 55, 110),
        "overlay": (12, 35, 75),
        "overlay_alpha": 105,
        "glass_alpha": 175,
    },
    "style.bold": {
        "name": "Violet Checklist",
        "bg": (250, 245, 255),
        "card": (255, 255, 255),
        "accent": (95, 45, 165),
        "accent2": (145, 80, 220),
        "text": (36, 24, 55),
        "muted": (110, 95, 130),
        "bar": (95, 45, 165),
        "overlay": (70, 25, 120),
        "overlay_alpha": 120,
        "glass_alpha": 168,
    },
    "style.soft": {
        "name": "Soft Blue Card",
        "bg": (235, 245, 255),
        "card": (255, 255, 255),
        "accent": (70, 135, 200),
        "accent2": (120, 180, 230),
        "text": (42, 58, 78),
        "muted": (105, 125, 145),
        "bar": (70, 135, 200),
        "overlay": (55, 110, 170),
        "overlay_alpha": 95,
        "glass_alpha": 182,
    },
}


def style_label(style_id: str) -> str:
    s = STYLES.get(style_id)
    if not s:
        return style_id
    return f"{s['name']} ({style_id})"

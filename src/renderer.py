"""Pillow 기반 1080x1080 Instagram 카드뉴스 — 포토 배경 + 소프트 폰트."""

from __future__ import annotations

import hashlib
import re
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .backgrounds import (
    fetch_topic_photo,
    prepare_body_bg,
    prepare_cover_bg,
    prepare_cta_bg,
    slide_photo_keywords,
)
from .presets import STYLES

SIZE = 1080
MARGIN = 64

ROOT = Path(__file__).resolve().parent.parent
FONTS_DIR = ROOT / "assets" / "fonts"

# weight -> preferred filenames under assets/fonts/
_FONT_FILES = {
    "regular": ["Pretendard-Regular.otf", "Pretendard-Regular.ttf", "NotoSansKR-Regular.otf"],
    "medium": ["Pretendard-Medium.otf", "Pretendard-Medium.ttf", "NotoSansKR-Medium.otf"],
    "semibold": ["Pretendard-SemiBold.otf", "Pretendard-SemiBold.ttf", "NotoSansKR-Bold.otf"],
    "bold": ["Pretendard-Bold.otf", "Pretendard-Bold.ttf", "NotoSansKR-Bold.otf"],
}

_SYSTEM_FALLBACK = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
]

# Curiosity / benefit hooks: (topic, audience) overrides, then topic, then audience, then generic.
_COVER_HOOKS_PAIR: dict[tuple[str, str], str] = {
    ("신메뉴", "직장인"): "오후 3시, 이 한 잔이면 달라져요",
    ("신메뉴", "자취생"): "집에서 카페 기분, 첫 모금에 반해요",
    ("신메뉴", "직장맘"): "잠깐의 여유, 이 메뉴로 채워보세요",
    ("꿀팁", "직장인"): "지금 바로 써먹는 직장인 꿀팁",
    ("꿀팁", "자취생"): "자취생이 몰라서 손해 보는 팁",
    ("꿀팁", "학부모"): "아이 일상, 이렇게만 바꿔보세요",
    ("후기", "입문자"): "써보니 달랐어요 — 솔직 후기",
    ("이벤트", "동네 주민"): "이번 주만, 놓치면 아쉬운 혜택",
    ("할인/프로모", "사장님"): "손님 발길 붙잡는 할인 포인트",
    ("혜택가이드", "직장맘"): "바쁜 하루, 혜택만 쏙쏙 정리",
    ("사용법", "입문자"): "처음이어도 3분이면 끝나요",
    ("전후", "입문자"): "전·후 차이, 사진으로 확인해 보세요",
    ("공지", "학부모"): "꼭 알아야 할 공지, 한눈에",
}

_COVER_HOOKS_TOPIC: dict[str, list[str]] = {
    "신메뉴": [
        "{audience}이 먼저 찾는 그 맛",
        "새로 나왔어요 — 궁금하지 않나요?",
        "한 모금에 반하는 {topic}",
    ],
    "꿀팁": [
        "{audience}이 몰래 쓰는 {topic}",
        "알면 이득, 모르면 손해",
        "오늘부터 바로 쓰는 팁",
    ],
    "후기": [
        "직접 써본 솔직 후기",
        "{audience} 반응이 좋은 이유",
        "별점보다 생생한 이야기",
    ],
    "이벤트": [
        "지금만 가능한 기회",
        "{audience} 위한 깜짝 혜택",
        "저장해 두고 참여하세요",
    ],
    "공지": [
        "놓치면 아쉬운 소식",
        "{audience}이 꼭 확인하세요",
        "짧게, 핵심만 정리했어요",
    ],
    "전후": [
        "변화, 눈으로 확인하세요",
        "전·후가 말해 주는 차이",
        "{audience}이 놀란 결과",
    ],
    "사용법": [
        "따라만 하면 되는 사용법",
        "초보도 OK, 단계별 가이드",
        "오늘 바로 적용해 보세요",
    ],
    "할인/프로모": [
        "혜택, 지금이 타이밍",
        "{audience} 지갑 사수 팁",
        "할인 포인트만 모아봤어요",
    ],
    "혜택가이드": [
        "혜택만 쏙쏙, 한 장 요약",
        "{audience} 맞춤 혜택 가이드",
        "알아두면 이득인 혜택",
    ],
}

_COVER_HOOKS_AUDIENCE: dict[str, list[str]] = {
    "직장맘": ["바쁜 하루, 이것만은 챙기세요", "육아·업무 사이 작은 여유"],
    "자취생": ["자취생 필수, 이것부터", "혼라이프가 편해지는 한 가지"],
    "사장님": ["손님 반응이 달라지는 포인트", "매출에 도움 되는 한 줄 요약"],
    "입문자": ["처음이어도 어렵지 않아요", "입문자가 가장 먼저 볼 내용"],
    "학부모": ["아이 위해 알아두면 좋은 정보", "학부모 공감 100%"],
    "직장인": ["퇴근 전 3분이면 충분해요", "직장인이 저장하는 이유"],
    "동네 주민": ["우리 동네 소식, 핵심만", "근처라면 꼭 보세요"],
    "학생": ["과제보다 먼저 볼 카드", "학생이 공감하는 포인트"],
}

_GENERIC_HOOKS = [
    "{audience}이라면 한번 보세요",
    "{topic}, 궁금증 여기서 풀어요",
    "스크롤 멈추게 하는 {topic}",
    "저장해 두고 나중에 보세요",
]

# Soft engagement CTAs tailored by audience (Korean).
_CTA_BY_AUDIENCE: dict[str, dict[str, str]] = {
    "직장인": {
        "title": "동료에게도 살짝 공유해요",
        "subtitle": "커피 타임에 다시 꺼내볼 수 있게 저장해 두세요",
        "body": "도움이 됐다면 ❤️ · 취향은 댓글로 · 팔로우하면 다음 카드도",
    },
    "직장맘": {
        "title": "같은 맘 친구에게 전해 주세요",
        "subtitle": "바쁜 하루, 필요할 때 꺼내보도록 저장해요",
        "body": "공감되면 ❤️ · 육아 팁은 댓글로 · 팔로우하고 다음 소식 받기",
    },
    "자취생": {
        "title": "자취 메이트에게도 공유해요",
        "subtitle": "나중에 다시 볼 수 있게 저장해 두세요",
        "body": "유용했다면 ❤️ · 꿀팁은 댓글로 · 팔로우하면 더 받아요",
    },
    "사장님": {
        "title": "사장님 커뮤니티에 공유해 보세요",
        "subtitle": "매장 운영에 참고하도록 저장해 두세요",
        "body": "도움 됐다면 ❤️ · 현장 후기는 댓글로 · 팔로우하고 팁 더 받기",
    },
    "입문자": {
        "title": "입문 친구에게도 알려 주세요",
        "subtitle": "복습할 때 꺼내보도록 저장해 두세요",
        "body": "이해가 됐다면 ❤️ · 궁금한 점은 댓글로 · 팔로우하면 이어져요",
    },
    "학부모": {
        "title": "학부모 단톡에도 공유해 보세요",
        "subtitle": "필요할 때 다시 보도록 저장해 두세요",
        "body": "공감되면 ❤️ · 경험은 댓글로 · 팔로우하고 다음 가이드 받기",
    },
    "동네 주민": {
        "title": "이웃에게도 전해 주세요",
        "subtitle": "동네 소식, 필요할 때 꺼내보도록 저장해요",
        "body": "유익했다면 ❤️ · 동네 정보는 댓글로 · 팔로우하면 소식 이어져요",
    },
    "학생": {
        "title": "친구에게도 공유해 보세요",
        "subtitle": "시험·과제 전에 다시 보도록 저장해요",
        "body": "도움 됐다면 ❤️ · 질문은 댓글로 · 팔로우하고 다음 카드 받기",
    },
}

_CTA_DEFAULT = {
    "title": "저장하고 공유해 보세요",
    "subtitle": "필요할 때 다시 꺼내볼 수 있어요",
    "body": "도움이 됐다면 ❤️ · 생각은 댓글로 · 팔로우하면 다음 카드도",
}


def _font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Bundled Pretendard first (soft/modern), then system fallbacks."""
    names = _FONT_FILES.get(weight, _FONT_FILES["regular"])
    if weight == "bold":
        names = names + _FONT_FILES["semibold"] + _FONT_FILES["medium"]
    elif weight == "semibold":
        names = names + _FONT_FILES["medium"] + _FONT_FILES["bold"]
    for name in names:
        path = FONTS_DIR / name
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    for path in _SYSTEM_FALLBACK:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for para in text.splitlines() or [""]:
        if not para.strip():
            lines.append("")
            continue
        wrapped = textwrap.wrap(para, width=width) or [para]
        lines.extend(wrapped)
    return lines


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _pick_template(templates: list[str], seed: str) -> str:
    if not templates:
        return ""
    idx = int(hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8], 16) % len(templates)
    return templates[idx]


def cover_hook(topic: str, audience: str) -> str:
    """Short curiosity/benefit hook for cover — no paid LLM."""
    pair = _COVER_HOOKS_PAIR.get((topic, audience))
    if pair:
        return pair
    topic_list = _COVER_HOOKS_TOPIC.get(topic)
    if topic_list:
        tmpl = _pick_template(topic_list, f"{topic}|{audience}|cover")
        return tmpl.format(topic=topic, audience=audience)
    aud_list = _COVER_HOOKS_AUDIENCE.get(audience)
    if aud_list:
        tmpl = _pick_template(aud_list, f"{audience}|{topic}|cover")
        return tmpl.format(topic=topic, audience=audience)
    tmpl = _pick_template(_GENERIC_HOOKS, f"{topic}|{audience}")
    return tmpl.format(topic=topic, audience=audience)


def cta_copy(audience: str, topic: str) -> dict[str, str]:
    """Soft engagement CTA tailored to audience label."""
    base = dict(_CTA_BY_AUDIENCE.get(audience, _CTA_DEFAULT))
    # Keep hashtag soft on subtitle line end via caller if needed
    return base


def _split_source(source: str, max_slides: int = 8, min_slides: int = 5) -> list[dict[str, str]]:
    """소스 텍스트를 슬라이드용 청크로 분할."""
    raw = source.strip()
    if not raw:
        raw = (
            "내용을 입력해 주세요.\n핵심 메시지를 간단히 정리합니다.\n"
            "실천 팁을 추가합니다.\n요약으로 마무리합니다.\n다음 액션을 안내합니다."
        )

    parts = re.split(r"\n\s*\n+|\n(?=\d+[\.\)]\s)|(?<=\n)(?=[•\-·]\s)", raw)
    parts = [p.strip() for p in parts if p and p.strip()]
    if len(parts) < 2:
        sentences = re.split(r"(?<=[.!?。！？])\s+|\n+", raw)
        parts = [s.strip() for s in sentences if s.strip()]

    if not parts:
        parts = [raw]

    body_budget = max(min_slides - 2, 1)
    body_budget = min(body_budget, max_slides - 2)

    if len(parts) > body_budget:
        chunk_size = (len(parts) + body_budget - 1) // body_budget
        merged = []
        for i in range(0, len(parts), chunk_size):
            merged.append("\n".join(parts[i : i + chunk_size]))
        parts = merged[:body_budget]

    slides: list[dict[str, str]] = []
    for i, chunk in enumerate(parts):
        title_line = chunk.split("\n", 1)[0][:40]
        slides.append({"role": "body", "title": title_line, "body": chunk, "index": i})
    return slides


def build_slide_plan(
    topic: str,
    audience: str,
    source: str,
    style_id: str,
    profile_name: str = "",
) -> list[dict[str, Any]]:
    """5~8장 슬라이드 플랜 생성."""
    style = STYLES.get(style_id, STYLES["style.clean"])
    bodies = _split_source(source, max_slides=8, min_slides=5)
    hook = cover_hook(topic, audience)
    cta = cta_copy(audience, topic)

    plan: list[dict[str, Any]] = []
    plan.append(
        {
            "role": "cover",
            "title": hook,
            "subtitle": topic,  # topic as small label, not bland audience line
            "body": profile_name or "",
            "style": style,
            "style_id": style_id,
            "topic": topic,
            "audience": audience,
        }
    )
    for b in bodies:
        plan.append(
            {
                "role": "body",
                "title": b["title"],
                "body": b["body"],
                "style": style,
                "style_id": style_id,
                "topic": topic,
                "audience": audience,
            }
        )
    plan.append(
        {
            "role": "cta",
            "title": cta["title"],
            "subtitle": cta["subtitle"],
            "body": cta["body"],
            "style": style,
            "style_id": style_id,
            "topic": topic,
            "audience": audience,
        }
    )

    while len(plan) < 5:
        plan.insert(
            -1,
            {
                "role": "body",
                "title": "핵심 포인트",
                "body": "핵심 내용을 한 줄로 정리해 전달합니다.\n독자가 바로 이해할 수 있게 짧게 씁니다.",
                "style": style,
                "style_id": style_id,
                "topic": topic,
                "audience": audience,
            },
        )
    if len(plan) > 8:
        keep_body = 6
        plan = [plan[0]] + plan[1 : 1 + keep_body] + [plan[-1]]

    for i, s in enumerate(plan):
        s["page"] = i + 1
        s["total"] = len(plan)
        s["photo_keywords"] = slide_photo_keywords(
            topic=topic,
            audience=audience,
            title=str(s.get("title", "")),
            body=str(s.get("body", "")),
            page=s["page"],
            role=str(s.get("role", "body")),
        )
    return plan


def _pill(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    text_fill: tuple[int, int, int] = (255, 255, 255),
    pad_x: int = 18,
    pad_y: int = 10,
) -> int:
    tw, th = _text_size(draw, text, font)
    x, y = xy
    box = (x, y, x + tw + pad_x * 2, y + th + pad_y * 2)
    draw.rounded_rectangle(box, radius=(th + pad_y * 2) // 2, fill=fill)
    draw.text((x + pad_x, y + pad_y - 2), text, font=font, fill=text_fill)
    return box[3]


def _draw_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int] | tuple[int, int, int, int],
    shadow: bool = True,
) -> int:
    """Draw one centered line; return next y."""
    tw, th = _text_size(draw, text, font)
    x = (SIZE - tw) // 2
    if shadow:
        draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 160))
    draw.text((x, y), text, font=font, fill=fill)
    return y + th + 10


def _draw_centered_block(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    start_y: int,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    line_gap: int = 12,
    shadow: bool = True,
    max_lines: int = 8,
) -> int:
    y = start_y
    for line in lines[:max_lines]:
        if not line.strip():
            y += int(font.size * 0.4) if hasattr(font, "size") else 16
            continue
        tw, th = _text_size(draw, line, font)
        x = (SIZE - tw) // 2
        if shadow:
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=fill)
        y += th + line_gap
    return y


def render_slide(slide: dict[str, Any], photo: Image.Image | None = None) -> Image.Image:
    style = slide["style"]
    role = slide.get("role", "body")
    tint = style.get("overlay", style["accent"])
    tint_a = int(style.get("overlay_alpha", 100))

    if photo is None:
        kw = slide.get("photo_keywords") or slide_photo_keywords(
            slide.get("topic", ""),
            slide.get("audience", ""),
            title=str(slide.get("title", "")),
            body=str(slide.get("body", "")),
            page=int(slide.get("page", 1)),
            role=role,
        )
        photo = fetch_topic_photo(
            kw,
            size=SIZE,
            fallback_colors=(style["accent"], style.get("accent2", style["accent"])),
        )

    if role == "cover":
        img = prepare_cover_bg(photo, SIZE, tint, tint_alpha=max(tint_a - 15, 55))
    elif role == "cta":
        img = prepare_cta_bg(photo, SIZE, tint, tint_alpha=tint_a)
    else:
        # style tint differences: clean / bold / soft via overlay_alpha in presets
        blur = 2.5 if slide.get("style_id") == "style.bold" else 3.5
        if slide.get("style_id") == "style.soft":
            blur = 4.5
        img = prepare_body_bg(photo, SIZE, tint, tint_alpha=tint_a, blur=blur)

    page = slide.get("page", 1)
    total = slide.get("total", 1)

    font_hook = _font(58, "bold")
    font_title = _font(44 if role == "cover" else 38, "semibold")
    font_sub = _font(28, "medium")
    font_body = _font(26, "regular")
    font_meta = _font(22, "medium")
    font_label = _font(20, "semibold")

    draw = ImageDraw.Draw(img)

    # page badge top-right (always)
    badge = f"{page} / {total}"
    bw, _ = _text_size(draw, badge, font_meta)
    draw.text((SIZE - MARGIN - bw, MARGIN + 14), badge, font=font_meta, fill=(255, 255, 255, 210))

    if role == "cover":
        # small accent pill top-left
        _pill(
            draw,
            (MARGIN, MARGIN + 8),
            "CARD NEWS",
            font_label,
            fill=style["accent"],
            text_fill=(255, 255, 255),
        )
        # audience chip (subtle)
        aud = str(slide.get("audience", "")).strip()
        if aud:
            _pill(
                draw,
                (MARGIN, MARGIN + 58),
                aud,
                font_label,
                fill=style.get("accent2", style["accent"]),
                text_fill=(255, 255, 255),
                pad_x=14,
                pad_y=8,
            )

        # Large hook in lower third, center-aligned
        y = int(SIZE * 0.62)
        hook_lines = _wrap(slide.get("title", ""), 12)
        y = _draw_centered_block(
            draw, hook_lines[:3], y, font_hook, (255, 255, 255), line_gap=14, max_lines=3
        )
        y += 8
        # topic as soft subtitle (not bland "X을 위한 카드뉴스")
        for line in _wrap(slide.get("subtitle", ""), 16)[:2]:
            y = _draw_centered(draw, line, y, font_sub, (230, 235, 245))
        if slide.get("body"):
            y += 10
            _draw_centered(draw, str(slide["body"]), y, font_meta, (200, 210, 225), shadow=False)
        draw.rectangle([0, SIZE - 10, SIZE, SIZE], fill=style["accent"])
        return img

    # Body / CTA — NO glass card. Lower-third, center-aligned (Instagram story).
    y = int(SIZE * 0.62) if role == "body" else int(SIZE * 0.56)

    if role == "cta":
        chip = "TOGETHER"
        tw, th = _text_size(draw, chip, font_label)
        pad_x, pad_y = 18, 10
        chip_w = tw + pad_x * 2
        chip_x = (SIZE - chip_w) // 2
        draw.rounded_rectangle(
            (chip_x, MARGIN + 8, chip_x + chip_w, MARGIN + 8 + th + pad_y * 2),
            radius=(th + pad_y * 2) // 2,
            fill=style["accent2"],
        )
        draw.text((chip_x + pad_x, MARGIN + 8 + pad_y - 2), chip, font=font_label, fill=(255, 255, 255))

        title_lines = _wrap(slide.get("title", ""), 14)
        y = _draw_centered_block(
            draw, title_lines[:3], y, font_title, (255, 255, 255), line_gap=12, max_lines=3
        )
        y += 10
        sub_lines = _wrap(slide.get("subtitle", ""), 18)
        y = _draw_centered_block(
            draw, sub_lines[:3], y, font_sub, (235, 240, 250), line_gap=8, max_lines=3
        )
        y += 16
        body_lines = _wrap(slide.get("body", ""), 22)
        _draw_centered_block(
            draw, body_lines[:4], y, font_body, (210, 218, 230), line_gap=8, max_lines=4
        )
    else:
        # small style chip centered near mid-upper of text block
        style_name = STYLES.get(slide.get("style_id", ""), {}).get("name", "GUIDE")
        chip = style_name.upper()[:18]
        tw, th = _text_size(draw, chip, font_label)
        pad_x, pad_y = 16, 8
        chip_w = tw + pad_x * 2
        chip_x = (SIZE - chip_w) // 2
        chip_y = y - 52
        draw.rounded_rectangle(
            (chip_x, chip_y, chip_x + chip_w, chip_y + th + pad_y * 2),
            radius=(th + pad_y * 2) // 2,
            fill=style["accent2"],
        )
        draw.text((chip_x + pad_x, chip_y + pad_y - 2), chip, font=font_label, fill=(255, 255, 255))

        title = slide.get("title", "")[:40]
        title_lines = _wrap(title, 14)
        y = _draw_centered_block(
            draw, title_lines[:3], y, font_title, (255, 255, 255), line_gap=10, max_lines=3
        )
        y += 12
        body = slide.get("body", "")
        # Prefer body without repeating title line
        body_text = body
        if body.startswith(title) and "\n" in body:
            body_text = body.split("\n", 1)[-1].strip() or body
        use_bullet = slide.get("style_id") == "style.bold"
        raw_lines = _wrap(body_text, 20)[:8]
        if use_bullet:
            raw_lines = [("•  " + ln if ln.strip() else ln) for ln in raw_lines]
        _draw_centered_block(
            draw, raw_lines, y, font_body, (235, 240, 248), line_gap=8, max_lines=8
        )

    draw.rectangle([0, SIZE - 8, SIZE, SIZE], fill=style["accent"])
    return img


def generate_cardnews(
    topic: str,
    audience: str,
    source: str,
    style_id: str,
    out_dir: Path,
    profile_name: str = "",
    run_id: str | None = None,
) -> list[Path]:
    """슬라이드 생성 후 PNG 경로 리스트 반환. 슬라이드마다 다른 배경 이미지."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = build_slide_plan(topic, audience, source, style_id, profile_name)
    style = STYLES.get(style_id, STYLES["style.clean"])
    run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    paths: list[Path] = []
    kw_log: list[str] = []
    seen_photo_hashes: set[str] = set()
    for slide in plan:
        kw = slide.get("photo_keywords") or slide_photo_keywords(
            topic,
            audience,
            title=str(slide.get("title", "")),
            body=str(slide.get("body", "")),
            page=int(slide.get("page", 1)),
            role=str(slide.get("role", "body")),
        )
        kw_log.append(kw)
        photo = fetch_topic_photo(
            kw,
            size=SIZE,
            fallback_colors=(style["accent"], style.get("accent2", style["accent"])),
            avoid_hashes=seen_photo_hashes,
        )
        seen_photo_hashes.add(hashlib.md5(photo.convert("RGB").tobytes()).hexdigest())
        img = render_slide(slide, photo=photo)
        path = out_dir / f"{run_id}_slide_{slide['page']:02d}.png"
        img.save(path, format="PNG", optimize=True)
        paths.append(path)
    manifest = out_dir / f"{run_id}_manifest.txt"
    with manifest.open("w", encoding="utf-8") as f:
        f.write(
            f"topic={topic}\naudience={audience}\nstyle={style_id}\n"
            f"slides={len(paths)}\n"
        )
        for i, (p, kw) in enumerate(zip(paths, kw_log), start=1):
            f.write(f"{p.name}\tkeywords={kw}\n")
    return paths

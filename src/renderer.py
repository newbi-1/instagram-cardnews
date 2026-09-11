"""Pillow 기반 1080x1080 Instagram 카드뉴스 — 포토 배경 + 소프트 폰트."""

from __future__ import annotations

import re
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .backgrounds import (
    fetch_topic_photo,
    photo_keywords,
    prepare_body_bg,
    prepare_cover_bg,
)
from .presets import STYLES

SIZE = 1080
MARGIN = 64
CARD_PAD = 52
GLASS_RADIUS = 40

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


def _font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Bundled Pretendard first (soft/modern), then system fallbacks."""
    names = _FONT_FILES.get(weight, _FONT_FILES["regular"])
    # also try heavier ladders if missing
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

    plan: list[dict[str, Any]] = []
    plan.append(
        {
            "role": "cover",
            "title": topic,
            "subtitle": f"{audience}을(를) 위한 카드뉴스",
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
            "title": "저장하고 공유해 보세요",
            "subtitle": f"#{topic} #{audience}",
            "body": "더 많은 카드뉴스는 프로필에서 확인하세요.",
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
    return plan


def _paste_glass(
    base: Image.Image,
    xy: tuple[int, int, int, int],
    radius: int = GLASS_RADIUS,
    fill: tuple[int, int, int, int] = (255, 255, 255, 210),
    border: tuple[int, int, int, int] | None = (255, 255, 255, 90),
) -> Image.Image:
    """Soft translucent rounded glass panel over photo + light shadow."""

    out = base.convert("RGBA")
    # soft drop shadow
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sx0, sy0, sx1, sy1 = xy
    sd.rounded_rectangle((sx0 + 6, sy0 + 10, sx1 + 6, sy1 + 10), radius=radius, fill=(0, 0, 0, 70))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=12))
    out = Image.alpha_composite(out, shadow)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=border, width=2)
    return Image.alpha_composite(out, layer)


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


def render_slide(slide: dict[str, Any], photo: Image.Image | None = None) -> Image.Image:
    style = slide["style"]
    role = slide.get("role", "body")
    tint = style.get("overlay", style["accent"])
    tint_a = int(style.get("overlay_alpha", 100))

    if photo is None:
        kw = photo_keywords(slide.get("topic", ""), slide.get("audience", ""))
        photo = fetch_topic_photo(
            kw,
            size=SIZE,
            fallback_colors=(style["accent"], style.get("accent2", style["accent"])),
        )

    if role == "cover":
        img = prepare_cover_bg(photo, SIZE, tint, tint_alpha=max(tint_a - 20, 60))
    else:
        img = prepare_body_bg(photo, SIZE, tint, tint_alpha=tint_a, blur=5.0)

    page = slide.get("page", 1)
    total = slide.get("total", 1)

    font_title = _font(64 if role == "cover" else 42, "bold" if role == "cover" else "semibold")
    font_sub = _font(30, "medium")
    font_body = _font(28, "regular")
    font_meta = _font(22, "medium")
    font_label = _font(20, "semibold")

    if role == "cover":
        draw = ImageDraw.Draw(img)
        # accent pill top-left
        _pill(
            draw,
            (MARGIN, MARGIN + 8),
            "CARD NEWS",
            font_label,
            fill=style["accent"],
            text_fill=(255, 255, 255),
        )
        # page
        badge = f"{page} / {total}"
        bw, _ = _text_size(draw, badge, font_meta)
        draw.text((SIZE - MARGIN - bw, MARGIN + 18), badge, font=font_meta, fill=(255, 255, 255, 220))

        # large soft title near bottom third
        y = SIZE // 2 + 40
        title_lines = _wrap(slide.get("title", ""), 10)
        for line in title_lines[:4]:
            # soft shadow
            draw.text((MARGIN + 2, y + 2), line, font=font_title, fill=(0, 0, 0))
            draw.text((MARGIN, y), line, font=font_title, fill=(255, 255, 255))
            y += 78
        y += 12
        for line in _wrap(slide.get("subtitle", ""), 18)[:3]:
            draw.text((MARGIN, y), line, font=font_sub, fill=(235, 240, 250))
            y += 42
        if slide.get("body"):
            y += 18
            draw.text((MARGIN, y), str(slide["body"]), font=font_meta, fill=(200, 210, 225))
        # thin accent bar at bottom
        draw.rectangle([0, SIZE - 10, SIZE, SIZE], fill=style["accent"])
        return img

    # Body / CTA — glass card
    card_box = (MARGIN, MARGIN + 28, SIZE - MARGIN, SIZE - MARGIN - 36)
    img_rgba = _paste_glass(
        img,
        card_box,
        radius=GLASS_RADIUS,
        fill=(255, 255, 255, int(style.get("glass_alpha", 220))),
        border=(255, 255, 255, 100),
    )
    # subtle accent edge on left of glass
    accent_layer = Image.new("RGBA", img_rgba.size, (0, 0, 0, 0))
    ad = ImageDraw.Draw(accent_layer)
    ax0 = MARGIN + 10
    ad.rounded_rectangle(
        (ax0, MARGIN + 48, ax0 + 8, SIZE - MARGIN - 56),
        radius=4,
        fill=(*style["accent"], 230),
    )
    img_rgba = Image.alpha_composite(img_rgba, accent_layer)
    img = img_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    x0 = MARGIN + CARD_PAD
    y = MARGIN + 56
    max_y = SIZE - MARGIN - 70

    # page badge (muted on glass)
    badge = f"{page} / {total}"
    bw, _ = _text_size(draw, badge, font_meta)
    draw.text((SIZE - MARGIN - CARD_PAD - bw + 8, y), badge, font=font_meta, fill=style["muted"])

    if role == "cta":
        _pill(draw, (x0, y), "NEXT STEP", font_label, fill=style["accent2"])
        y += 56
        for line in _wrap(slide.get("title", ""), 12)[:3]:
            draw.text((x0, y), line, font=font_title, fill=style["accent"])
            y += 56
        y += 10
        for line in _wrap(slide.get("subtitle", ""), 18)[:2]:
            draw.text((x0, y), line, font=font_sub, fill=style["text"])
            y += 40
        y += 16
        for line in _wrap(slide.get("body", ""), 20)[:4]:
            if y > max_y:
                break
            draw.text((x0, y), line, font=font_body, fill=style["muted"])
            y += 38
    else:
        style_name = STYLES.get(slide.get("style_id", ""), {}).get("name", "GUIDE")
        _pill(draw, (x0, y), style_name.upper()[:18], font_label, fill=style["accent2"])
        y += 56
        title = slide.get("title", "")[:36]
        for line in _wrap(title, 14)[:3]:
            draw.text((x0, y), line, font=font_title, fill=style["accent"])
            y += 52
        y += 14
        body = slide.get("body", "")
        lines = _wrap(body, 22)[:11]
        use_bullet = slide.get("style_id") == "style.bold"
        for line in lines:
            if y > max_y:
                break
            prefix = "•  " if use_bullet and line.strip() else ""
            draw.text((x0, y), prefix + line, font=font_body, fill=style["text"])
            y += 40

    # soft bottom accent strip (style differentiation)
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
    """슬라이드 생성 후 PNG 경로 리스트 반환."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = build_slide_plan(topic, audience, source, style_id, profile_name)
    style = STYLES.get(style_id, STYLES["style.clean"])
    keywords = photo_keywords(topic, audience)
    photo = fetch_topic_photo(
        keywords,
        size=SIZE,
        fallback_colors=(style["accent"], style.get("accent2", style["accent"])),
    )
    run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    paths: list[Path] = []
    for slide in plan:
        img = render_slide(slide, photo=photo)
        path = out_dir / f"{run_id}_slide_{slide['page']:02d}.png"
        img.save(path, format="PNG", optimize=True)
        paths.append(path)
    manifest = out_dir / f"{run_id}_manifest.txt"
    with manifest.open("w", encoding="utf-8") as f:
        f.write(
            f"topic={topic}\naudience={audience}\nstyle={style_id}\n"
            f"photo_keywords={keywords}\nslides={len(paths)}\n"
        )
        for p in paths:
            f.write(f"{p.name}\n")
    return paths

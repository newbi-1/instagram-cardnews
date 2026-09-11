"""Pillow 기반 1080x1080 Instagram 카드뉴스 슬라이드 생성."""

from __future__ import annotations

import re
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .presets import STYLES

SIZE = 1080
MARGIN = 72
CARD_PAD = 48


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """시스템 한글 가능 폰트 탐색 (없으면 기본)."""
    candidates = []
    if bold:
        candidates += [
            "/usr/share/fonts/truetype/sand-box/google/Nanum Gothic/NanumGothic-Bold.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/malgunbd.ttf",
            "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        ]
    candidates += [
        "/usr/share/fonts/truetype/sand-box/google/Nanum Gothic/NanumGothic-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/malgun.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                # TTC may need face index; try default then KR index
                return ImageFont.truetype(path, size=size)
            except OSError:
                try:
                    return ImageFont.truetype(path, size=size, index=0)
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


def _split_source(source: str, max_slides: int = 8, min_slides: int = 5) -> list[dict[str, str]]:
    """소스 텍스트를 슬라이드용 청크로 분할."""
    raw = source.strip()
    if not raw:
        raw = "내용을 입력해 주세요.\n핵심 메시지를 간단히 정리합니다.\n실천 팁을 추가합니다.\n요약으로 마무리합니다.\n다음 액션을 안내합니다."

    # 번호/불릿/빈줄 기준 분할
    parts = re.split(r"\n\s*\n+|\n(?=\d+[\.\)]\s)|(?<=\n)(?=[•\-·]\s)", raw)
    parts = [p.strip() for p in parts if p and p.strip()]
    if len(parts) < 2:
        # 문장 단위
        sentences = re.split(r"(?<=[.!?。！？])\s+|\n+", raw)
        parts = [s.strip() for s in sentences if s.strip()]

    if not parts:
        parts = [raw]

    # 목표 슬라이드 수: 커버 + 본문 + CTA ≈ 5~8
    body_budget = max(min_slides - 2, 1)
    body_budget = min(body_budget, max_slides - 2)

    if len(parts) > body_budget:
        # 묶기
        chunk_size = (len(parts) + body_budget - 1) // body_budget
        merged = []
        for i in range(0, len(parts), chunk_size):
            merged.append("\n".join(parts[i : i + chunk_size]))
        parts = merged[:body_budget]
    elif len(parts) < body_budget:
        # 부족하면 패딩 힌트 문구로 채우지 않고 그대로 사용 (커버/CTA로 맞춤)
        pass

    slides: list[dict[str, str]] = []
    for i, chunk in enumerate(parts):
        title_line = chunk.split("\n", 1)[0][:40]
        body = chunk
        slides.append({"role": "body", "title": title_line, "body": body, "index": i})
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
    # Cover
    plan.append(
        {
            "role": "cover",
            "title": topic,
            "subtitle": f"{audience}을(를) 위한 카드뉴스",
            "body": profile_name or "",
            "style": style,
            "style_id": style_id,
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
            }
        )
    # CTA / outro
    plan.append(
        {
            "role": "cta",
            "title": "저장하고 공유해 보세요",
            "subtitle": f"#{topic} #{audience}",
            "body": "더 많은 카드뉴스는 프로필에서 확인하세요.",
            "style": style,
            "style_id": style_id,
        }
    )

    # Clamp 5~8
    while len(plan) < 5:
        plan.insert(
            -1,
            {
                "role": "body",
                "title": "핵심 포인트",
                "body": "핵심 내용을 한 줄로 정리해 전달합니다.\n독자가 바로 이해할 수 있게 짧게 씁니다.",
                "style": style,
                "style_id": style_id,
            },
        )
    if len(plan) > 8:
        # keep cover + first N bodies + cta
        keep_body = 6
        plan = [plan[0]] + plan[1 : 1 + keep_body] + [plan[-1]]

    for i, s in enumerate(plan):
        s["page"] = i + 1
        s["total"] = len(plan)
    return plan


def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int],
) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def render_slide(slide: dict[str, Any]) -> Image.Image:
    style = slide["style"]
    img = Image.new("RGB", (SIZE, SIZE), style["bg"])
    draw = ImageDraw.Draw(img)

    # Top accent bar
    draw.rectangle([0, 0, SIZE, 18], fill=style["bar"])

    # Card panel
    _draw_rounded_rect(
        draw,
        (MARGIN, MARGIN + 20, SIZE - MARGIN, SIZE - MARGIN - 40),
        radius=36,
        fill=style["card"],
    )

    # Accent stripe on card
    draw.rectangle(
        [MARGIN, MARGIN + 20, MARGIN + 16, SIZE - MARGIN - 40],
        fill=style["accent"],
    )

    page = slide.get("page", 1)
    total = slide.get("total", 1)
    role = slide.get("role", "body")

    font_title = _font(56 if role == "cover" else 44, bold=True)
    font_sub = _font(32, bold=False)
    font_body = _font(30, bold=False)
    font_meta = _font(24, bold=False)

    x0 = MARGIN + CARD_PAD + 8
    y = MARGIN + 60

    # Page badge
    badge = f"{page} / {total}"
    draw.text((SIZE - MARGIN - 140, MARGIN + 40), badge, font=font_meta, fill=style["muted"])

    if role == "cover":
        draw.text((x0, y), "CARD NEWS", font=font_meta, fill=style["accent2"])
        y += 50
        for line in _wrap(slide.get("title", ""), 12):
            draw.text((x0, y), line, font=font_title, fill=style["accent"])
            y += 70
        y += 20
        for line in _wrap(slide.get("subtitle", ""), 18):
            draw.text((x0, y), line, font=font_sub, fill=style["text"])
            y += 44
        if slide.get("body"):
            y += 30
            draw.text((x0, y), str(slide["body"]), font=font_meta, fill=style["muted"])
    elif role == "cta":
        draw.text((x0, y), "NEXT STEP", font=font_meta, fill=style["accent2"])
        y += 50
        for line in _wrap(slide.get("title", ""), 14):
            draw.text((x0, y), line, font=font_title, fill=style["accent"])
            y += 68
        y += 16
        for line in _wrap(slide.get("subtitle", ""), 20):
            draw.text((x0, y), line, font=font_sub, fill=style["text"])
            y += 42
        y += 20
        for line in _wrap(slide.get("body", ""), 22):
            draw.text((x0, y), line, font=font_body, fill=style["muted"])
            y += 40
    else:
        # body
        style_name = STYLES.get(slide.get("style_id", ""), {}).get("name", "")
        draw.text((x0, y), style_name or "GUIDE", font=font_meta, fill=style["accent2"])
        y += 48
        title = slide.get("title", "")[:36]
        for line in _wrap(title, 16):
            draw.text((x0, y), line, font=font_title, fill=style["accent"])
            y += 58
        y += 12
        # checklist bullets for bold style
        body = slide.get("body", "")
        lines = _wrap(body, 24)[:12]
        for line in lines:
            prefix = "• " if slide.get("style_id") == "style.bold" else ""
            draw.text((x0, y), prefix + line, font=font_body, fill=style["text"])
            y += 42
            if y > SIZE - MARGIN - 80:
                break

    # Footer bar
    draw.rectangle([0, SIZE - 28, SIZE, SIZE], fill=style["bar"])
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
    run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    paths: list[Path] = []
    for slide in plan:
        img = render_slide(slide)
        path = out_dir / f"{run_id}_slide_{slide['page']:02d}.png"
        img.save(path, format="PNG", optimize=True)
        paths.append(path)
    # manifest
    manifest = out_dir / f"{run_id}_manifest.txt"
    with manifest.open("w", encoding="utf-8") as f:
        f.write(f"topic={topic}\naudience={audience}\nstyle={style_id}\nslides={len(paths)}\n")
        for p in paths:
            f.write(f"{p.name}\n")
    return paths

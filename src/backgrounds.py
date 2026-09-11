"""Free no-key topic photo fetch + soft gradient fallback (Pillow only)."""

from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path
from typing import Iterable

import requests
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "assets" / "cache"

# Korean topic/audience -> English tags for loremflickr (no API key).
TOPIC_TAGS: dict[str, str] = {
    "신메뉴": "latte,coffee,cafe",
    "후기": "happy,customer,lifestyle",
    "이벤트": "party,celebration,balloon",
    "꿀팁": "notebook,desk,planner",
    "공지": "bulletin,office,workspace",
    "전후": "makeup,beauty,skincare",
    "사용법": "hands,tutorial,product",
    "할인/프로모": "shopping,sale,gift",
    "혜택가이드": "checklist,planner,notes",
}

AUDIENCE_TAGS: dict[str, str] = {
    "직장맘": "family,morning,home",
    "자취생": "apartment,cooking,cozy",
    "사장님": "business,store,shop",
    "입문자": "beginner,learning,book",
    "학부모": "school,parent,kids",
    "직장인": "office,coffee,city",
    "동네 주민": "neighborhood,street,community",
    "학생": "campus,study,books",
}

DEFAULT_TAGS = "lifestyle,minimal,aesthetic"


def photo_keywords(topic: str, audience: str = "") -> str:
    """Build English comma-tags for free photo search."""
    parts: list[str] = []
    if topic in TOPIC_TAGS:
        parts.extend(TOPIC_TAGS[topic].split(","))
    else:
        slug = re.sub(r"[^a-zA-Z0-9]+", ",", topic).strip(",").lower()
        if slug:
            parts.extend([t for t in slug.split(",") if t])
    # one soft audience hint only (topic stays dominant)
    if audience in AUDIENCE_TAGS:
        parts.append(AUDIENCE_TAGS[audience].split(",")[0])
    cleaned: list[str] = []
    for t in parts:
        t = t.strip().lower()
        if t and t not in cleaned:
            cleaned.append(t)
    cleaned = cleaned[:3]
    return ",".join(cleaned) or DEFAULT_TAGS


def _cache_path(keywords: str, size: int) -> Path:
    key = hashlib.sha1(f"{keywords}:{size}".encode()).hexdigest()[:16]
    safe = re.sub(r"[^a-z0-9,]+", "-", keywords.lower())[:40]
    return CACHE_DIR / f"{safe}_{key}_{size}.jpg"


def soft_gradient(size: int, colors: Iterable[tuple[int, int, int]]) -> Image.Image:
    """Fast diagonal soft gradient fallback (no network)."""
    palette = list(colors)
    if len(palette) < 2:
        palette = [(40, 60, 100), (120, 150, 200)]
    c0, c1 = palette[0], palette[-1]
    # 2x2 corner blend then upscale — soft aesthetic, cheap
    tiny = Image.new("RGB", (2, 2))
    tiny.putpixel((0, 0), c0)
    tiny.putpixel((1, 0), tuple((a + b) // 2 for a, b in zip(c0, c1)))
    tiny.putpixel((0, 1), tuple((a + b) // 2 for a, b in zip(c0, c1)))
    tiny.putpixel((1, 1), c1)
    return tiny.resize((size, size), Image.Resampling.BICUBIC).filter(
        ImageFilter.GaussianBlur(radius=1)
    )


def fetch_topic_photo(
    keywords: str,
    size: int = 1080,
    timeout: float = 8.0,
    fallback_colors: Iterable[tuple[int, int, int]] | None = None,
) -> Image.Image:
    """Download/cache a square photo from loremflickr; soft gradient on failure."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(keywords, size)
    if path.exists() and path.stat().st_size > 2000:
        try:
            return Image.open(path).convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
        except OSError:
            pass

    lock = int(hashlib.sha1(keywords.encode()).hexdigest()[:8], 16) % 100000
    url = f"https://loremflickr.com/{size}/{size}/{keywords}?lock={lock}"
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": "instagram-cardnews/1.0"},
        )
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        if img.size != (size, size):
            img = img.resize((size, size), Image.Resampling.LANCZOS)
        img.save(path, format="JPEG", quality=88, optimize=True)
        return img
    except Exception:
        colors = fallback_colors or ((35, 55, 95), (140, 170, 210))
        return soft_gradient(size, colors)


def cover_fit(photo: Image.Image, size: int) -> Image.Image:
    """Center-crop / resize to square."""
    img = photo.convert("RGB")
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    if img.size != (size, size):
        img = img.resize((size, size), Image.Resampling.LANCZOS)
    return img


def vertical_gradient_mask(size: int, top_alpha: int = 40, bottom_alpha: int = 200) -> Image.Image:
    """Bottom-heavy darkening mask (RGBA)."""
    mask = Image.new("L", (1, size))
    for y in range(size):
        t = y / (size - 1)
        eased = t * t
        a = int(top_alpha + (bottom_alpha - top_alpha) * eased)
        mask.putpixel((0, y), a)
    mask = mask.resize((size, size), Image.Resampling.BILINEAR)
    rgba = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    rgba.putalpha(mask)
    return rgba


def prepare_cover_bg(
    photo: Image.Image,
    size: int,
    tint: tuple[int, int, int],
    tint_alpha: int = 90,
) -> Image.Image:
    base = cover_fit(photo, size).convert("RGBA")
    tint_layer = Image.new("RGBA", (size, size), (*tint, tint_alpha))
    base = Image.alpha_composite(base, tint_layer)
    base = Image.alpha_composite(base, vertical_gradient_mask(size, 30, 210))
    return base.convert("RGB")


def prepare_body_bg(
    photo: Image.Image,
    size: int,
    tint: tuple[int, int, int],
    tint_alpha: int = 100,
    blur: float = 5.0,
) -> Image.Image:
    base = cover_fit(photo, size)
    base = base.filter(ImageFilter.GaussianBlur(radius=blur))
    base = base.convert("RGBA")
    dark = Image.new("RGBA", (size, size), (0, 0, 0, 70))
    tint_layer = Image.new("RGBA", (size, size), (*tint, tint_alpha))
    base = Image.alpha_composite(base, dark)
    base = Image.alpha_composite(base, tint_layer)
    return base.convert("RGB")

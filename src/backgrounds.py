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

# Rich tag pools so each slide can pick a DISTINCT primary tag.
TOPIC_TAG_POOLS: dict[str, list[str]] = {
    "신메뉴": ["latte", "coffee", "cafe", "espresso", "cappuccino", "barista", "mug", "pastry"],
    "후기": ["happy", "smile", "lifestyle", "friends", "review", "customer", "portrait", "joy"],
    "이벤트": ["party", "celebration", "balloon", "confetti", "festival", "crowd", "lights", "stage"],
    "꿀팁": ["notebook", "desk", "planner", "sticky", "pen", "workspace", "laptop", "checklist"],
    "공지": ["bulletin", "office", "workspace", "meeting", "board", "sign", "paper", "desk"],
    "전후": ["makeup", "beauty", "skincare", "mirror", "cosmetics", "glow", "portrait", "studio"],
    "사용법": ["hands", "tutorial", "product", "demo", "howto", "tools", "craft", "guide"],
    "할인/프로모": ["shopping", "sale", "gift", "bag", "store", "retail", "coupon", "mall"],
    "혜택가이드": ["checklist", "planner", "notes", "calendar", "tablet", "documents", "folder", "pen"],
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

TOPIC_TAGS: dict[str, str] = {k: ",".join(v[:3]) for k, v in TOPIC_TAG_POOLS.items()}
DEFAULT_TAGS = "lifestyle,minimal,aesthetic"


def photo_keywords(topic: str, audience: str = "", concept_id: str | None = None) -> str:
    """Build English comma-tags for free photo search (concept-aware)."""
    parts: list[str] = []
    pool: list[str] | None = None
    if concept_id:
        try:
            from .concepts import photo_pool_for

            pool = photo_pool_for(concept_id, topic)
        except Exception:
            pool = None
    if pool:
        parts.extend(pool[:3])
    elif topic in TOPIC_TAG_POOLS:
        parts.extend(TOPIC_TAG_POOLS[topic][:3])
    else:
        slug = re.sub(r"[^a-zA-Z0-9]+", ",", topic).strip(",").lower()
        if slug:
            parts.extend([t for t in slug.split(",") if t])
    if audience in AUDIENCE_TAGS:
        parts.append(AUDIENCE_TAGS[audience].split(",")[0])
    cleaned: list[str] = []
    for t in parts:
        t = t.strip().lower()
        if t and t not in cleaned:
            cleaned.append(t)
    cleaned = cleaned[:3]
    return ",".join(cleaned) or DEFAULT_TAGS


def slide_photo_keywords(
    topic: str,
    audience: str = "",
    title: str = "",
    body: str = "",
    page: int = 1,
    role: str = "body",
    concept_id: str | None = None,
) -> str:
    """Unique real Flickr-style tags per slide (concept/topic pool + audience)."""
    pool: list[str] | None = None
    if concept_id:
        try:
            from .concepts import photo_pool_for

            pool = photo_pool_for(concept_id, topic)
        except Exception:
            pool = None
    if not pool:
        pool = list(TOPIC_TAG_POOLS.get(topic, DEFAULT_TAGS.split(",")))
    primary = pool[(max(page, 1) - 1) % len(pool)]
    secondary = pool[(max(page, 1)) % len(pool)]

    aud = ""
    if audience in AUDIENCE_TAGS:
        aud = AUDIENCE_TAGS[audience].split(",")[0]

    snippet = f"{concept_id or ''}|{role}|{title}|{body[:48]}|{page}".strip()
    token = hashlib.sha1(snippet.encode("utf-8")).hexdigest()
    tertiary = pool[int(token[:6], 16) % len(pool)]

    tags: list[str] = []
    for t in (primary, secondary, aud or tertiary):
        t = (t or "").strip().lower()
        if t and t not in tags:
            tags.append(t)
    tags.append(f"s{page}{token[:6]}")
    return ",".join(tags)


def _cache_path(keywords: str, size: int) -> Path:
    key = hashlib.sha1(f"{keywords}:{size}".encode()).hexdigest()[:16]
    safe = re.sub(r"[^a-z0-9,]+", "-", keywords.lower())[:50]
    return CACHE_DIR / f"{safe}_{key}_{size}.jpg"


def soft_gradient(size: int, colors: Iterable[tuple[int, int, int]]) -> Image.Image:
    """Fast diagonal soft gradient fallback (no network)."""
    palette = list(colors)
    if len(palette) < 2:
        palette = [(40, 60, 100), (120, 150, 200)]
    c0, c1 = palette[0], palette[-1]
    tiny = Image.new("RGB", (2, 2))
    tiny.putpixel((0, 0), c0)
    tiny.putpixel((1, 0), tuple((a + b) // 2 for a, b in zip(c0, c1)))
    tiny.putpixel((0, 1), tuple((a + b) // 2 for a, b in zip(c0, c1)))
    tiny.putpixel((1, 1), c1)
    return tiny.resize((size, size), Image.Resampling.BICUBIC).filter(
        ImageFilter.GaussianBlur(radius=1)
    )


def _content_hash(img: Image.Image) -> str:
    return hashlib.md5(img.convert("RGB").tobytes()).hexdigest()


def _download_loremflickr(url_tags: str, lock: int, size: int, timeout: float) -> Image.Image | None:
    url = f"https://loremflickr.com/{size}/{size}/{url_tags}?lock={lock}"
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
        return img
    except Exception:
        return None


def _download_picsum(seed: str, size: int, timeout: float) -> Image.Image | None:
    """Guaranteed-unique free photo by seed (no API key)."""
    url = f"https://picsum.photos/seed/{seed}/{size}/{size}"
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
        return img
    except Exception:
        return None


def fetch_topic_photo(
    keywords: str,
    size: int = 1080,
    timeout: float = 8.0,
    fallback_colors: Iterable[tuple[int, int, int]] | None = None,
    avoid_hashes: set[str] | None = None,
) -> Image.Image:
    """Download/cache a square photo; ensure uniqueness vs avoid_hashes when possible."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(keywords, size)
    avoid = avoid_hashes or set()

    if path.exists() and path.stat().st_size > 2000:
        try:
            cached = Image.open(path).convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
            if _content_hash(cached) not in avoid:
                return cached
        except OSError:
            pass

    url_tags = ",".join(
        t for t in keywords.split(",") if t and not re.match(r"^s\d", t)
    ) or DEFAULT_TAGS
    base_lock = int(hashlib.sha1(keywords.encode()).hexdigest()[:8], 16) % 100000

    img: Image.Image | None = None
    for attempt in range(4):
        lock = (base_lock + attempt * 9973) % 100000
        parts = url_tags.split(",")
        if attempt and len(parts) > 1:
            rotated = parts[attempt % len(parts) :] + parts[: attempt % len(parts)]
            try_tags = ",".join(rotated)
        else:
            try_tags = url_tags
        candidate = _download_loremflickr(try_tags, lock, size, timeout)
        if candidate is None:
            continue
        if _content_hash(candidate) in avoid:
            continue
        img = candidate
        break

    if img is None or _content_hash(img) in avoid:
        seed = hashlib.sha1(keywords.encode()).hexdigest()[:16]
        for n in range(3):
            candidate = _download_picsum(f"{seed}{n}", size, timeout)
            if candidate is None:
                continue
            if _content_hash(candidate) in avoid:
                continue
            img = candidate
            break

    if img is None:
        colors = fallback_colors or ((35, 55, 95), (140, 170, 210))
        seed_n = int(hashlib.sha1(keywords.encode()).hexdigest()[:4], 16)
        c_list = list(colors)
        shifted = tuple((c + (seed_n % 40) * (i + 1)) % 220 for i, c in enumerate(c_list[0]))
        img = soft_gradient(size, (shifted, c_list[-1]))

    try:
        img.save(path, format="JPEG", quality=88, optimize=True)
    except OSError:
        pass
    return img


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


def vertical_gradient_mask(
    size: int,
    top_alpha: int = 40,
    bottom_alpha: int = 200,
    start_ratio: float = 0.0,
) -> Image.Image:
    """Bottom-heavy darkening mask (RGBA). start_ratio: where fade begins (0=top)."""
    mask = Image.new("L", (1, size))
    start_y = int(size * max(0.0, min(0.95, start_ratio)))
    for y in range(size):
        if y < start_y:
            a = top_alpha
        else:
            t = (y - start_y) / max(size - 1 - start_y, 1)
            eased = t * t
            a = int(top_alpha + (bottom_alpha - top_alpha) * eased)
        mask.putpixel((0, y), max(0, min(255, a)))
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
    tint_layer = Image.new("RGBA", (size, size), (*tint, max(35, tint_alpha // 2)))
    base = Image.alpha_composite(base, tint_layer)
    base = Image.alpha_composite(base, vertical_gradient_mask(size, 0, 225, start_ratio=0.45))
    return base.convert("RGB")


def prepare_body_bg(
    photo: Image.Image,
    size: int,
    tint: tuple[int, int, int],
    tint_alpha: int = 70,
    blur: float = 3.5,
) -> Image.Image:
    """Instagram-story style: photo visible up top, dark gradient in lower third."""
    base = cover_fit(photo, size)
    if blur > 0:
        base = base.filter(ImageFilter.GaussianBlur(radius=blur))
    base = base.convert("RGBA")
    tint_layer = Image.new("RGBA", (size, size), (*tint, max(30, tint_alpha // 3)))
    base = Image.alpha_composite(base, tint_layer)
    base = Image.alpha_composite(
        base, vertical_gradient_mask(size, top_alpha=0, bottom_alpha=235, start_ratio=0.50)
    )
    return base.convert("RGB")


def prepare_cta_bg(
    photo: Image.Image,
    size: int,
    tint: tuple[int, int, int],
    tint_alpha: int = 80,
) -> Image.Image:
    """CTA: photo visible, stronger lower vignette for engagement copy."""
    base = cover_fit(photo, size).convert("RGBA")
    tint_layer = Image.new("RGBA", (size, size), (*tint, max(35, tint_alpha // 2)))
    base = Image.alpha_composite(base, tint_layer)
    base = Image.alpha_composite(
        base, vertical_gradient_mask(size, top_alpha=10, bottom_alpha=240, start_ratio=0.42)
    )
    return base.convert("RGB")

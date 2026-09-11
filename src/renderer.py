"""Pillow 기반 1080x1080 Instagram 카드뉴스 — 포토 배경 + 소프트 폰트."""

from __future__ import annotations

import hashlib
import re
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

# Drawable text region (lower-third, centered, padded) — used for real metric pagination.
TEXT_MAX_WIDTH = SIZE - 2 * MARGIN  # 952
BODY_TEXT_TOP = int(SIZE * 0.62)  # title starts here
CTA_TEXT_TOP = int(SIZE * 0.56)
TEXT_BOTTOM = SIZE - 48  # above accent bar; never draw past this
TITLE_LINE_GAP = 10
BODY_LINE_GAP = 8
TITLE_BODY_GAP = 12
CHIP_ABOVE = 52
MAX_TITLE_LINES_BODY = 2
MAX_BODY_LINES_SOFT = 10  # soft cap; height check is authoritative
MAX_TOTAL_SLIDES = 8
MIN_TOTAL_SLIDES = 5
CONTINUATION_MARK = "이어서"
SUMMARY_TITLE = "요약"

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
        "subtitle": "커피 타임에 다시 꺼내볼 수 있게, 저장해 두세요",
        "body": "도움이 됐다면 좋아요, 취향은 댓글로 남겨 주세요. 팔로우하면 다음 카드도 받아볼 수 있어요",
    },
    "직장맘": {
        "title": "같은 맘 친구에게 전해 주세요",
        "subtitle": "바쁜 하루, 필요할 때 꺼내보도록 저장해 두세요",
        "body": "공감되셨다면 좋아요, 육아 팁은 댓글로 나눠 주세요. 저장해 두고, 팔로우하면 다음 소식도 받아볼 수 있어요",
    },
    "자취생": {
        "title": "자취 메이트에게도 공유해요",
        "subtitle": "나중에 다시 볼 수 있게, 저장해 두세요",
        "body": "유용했다면 좋아요, 꿀팁은 댓글로 남겨 주세요. 팔로우하면 다음 카드도 받아볼 수 있어요",
    },
    "사장님": {
        "title": "사장님 커뮤니티에 공유해 보세요",
        "subtitle": "매장 운영에 참고하도록, 저장해 두세요",
        "body": "도움이 됐다면 좋아요, 현장 후기는 댓글로 남겨 주세요. 팔로우하면 운영 팁도 이어서 받아볼 수 있어요",
    },
    "입문자": {
        "title": "입문 친구에게도 알려 주세요",
        "subtitle": "복습할 때 꺼내볼 수 있게, 저장해 두세요",
        "body": "이해가 됐다면 좋아요, 궁금한 점은 댓글로 남겨 주세요. 팔로우하면 다음 카드도 이어져요",
    },
    "학부모": {
        "title": "학부모 단톡에도 공유해 보세요",
        "subtitle": "필요할 때 다시 볼 수 있게, 저장해 두세요",
        "body": "공감되셨다면 좋아요, 경험은 댓글로 남겨 주세요. 팔로우하면 다음 가이드도 받아볼 수 있어요",
    },
    "동네 주민": {
        "title": "이웃에게도 전해 주세요",
        "subtitle": "동네 소식, 필요할 때 꺼내보도록 저장해 두세요",
        "body": "유익했다면 좋아요, 동네 정보는 댓글로 남겨 주세요. 팔로우하면 다음 소식도 받아볼 수 있어요",
    },
    "학생": {
        "title": "친구에게도 공유해 보세요",
        "subtitle": "시험·과제 전에 다시 볼 수 있게, 저장해 두세요",
        "body": "도움이 됐다면 좋아요, 질문은 댓글로 남겨 주세요. 팔로우하면 다음 카드도 받아볼 수 있어요",
    },
}

_CTA_DEFAULT = {
    "title": "저장하고 공유해 보세요",
    "subtitle": "필요할 때 다시 꺼내볼 수 있어요",
    "body": "도움이 됐다면 좋아요, 생각은 댓글로 남겨 주세요. 저장해 두고, 팔로우하면 다음 카드도 받아볼 수 있어요",
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


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _measure(text: str, font: ImageFont.ImageFont, draw: ImageDraw.ImageDraw | None = None) -> tuple[int, int]:
    """Width/height via real font metrics (dummy draw if needed)."""
    if draw is None:
        draw = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    return _text_size(draw, text, font)


def _wrap_to_width(
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    draw: ImageDraw.ImageDraw | None = None,
) -> list[str]:
    """Wrap paragraphs to pixel width using font metrics — works for Korean and Latin."""
    if draw is None:
        draw = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    lines: list[str] = []
    for para in (text.splitlines() or [""]):
        if not para.strip():
            lines.append("")
            continue
        # Prefer space-aware wrap when spaces exist; otherwise char-cluster wrap.
        if " " in para and not _looks_cjk_heavy(para):
            lines.extend(_wrap_latin_words(para, font, max_width, draw))
        else:
            lines.extend(_wrap_cjk_chars(para, font, max_width, draw))
    return lines



def _hard_split_cover_hook(text: str) -> list[str]:
    """Cover hook only: hard-break after sentence/clause punctuation into segments.

    Always split *after* `.` `。` `!` `?` `！` `？` and `,` `，` `、`.
    Trim spaces; drop empty segments. Width-wrap still applied per segment.
    """
    raw = (text or "").strip()
    if not raw:
        return []
    # Keep punctuation with the preceding clause; allow optional trailing spaces.
    parts = re.split(r"(?<=[.。!?！？,，、])\s*", raw)
    return [p.strip() for p in parts if p and p.strip()]


def _looks_cjk_heavy(s: str) -> bool:
    cjk = sum(1 for ch in s if "\uac00" <= ch <= "\ud7a3" or "\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff")
    return cjk >= max(1, len(s) // 3)


def _wrap_latin_words(
    para: str,
    font: ImageFont.ImageFont,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> list[str]:
    words = para.split()
    if not words:
        return [""]
    out: list[str] = []
    cur = words[0]
    for w in words[1:]:
        trial = f"{cur} {w}"
        tw, _ = _text_size(draw, trial, font)
        if tw <= max_width:
            cur = trial
        else:
            out.append(cur)
            cur = w
            # hard-break oversized single word
            while True:
                tw, _ = _text_size(draw, cur, font)
                if tw <= max_width or len(cur) <= 1:
                    break
                # binary-ish cut
                cut = max(1, int(len(cur) * max_width / max(tw, 1)))
                while cut < len(cur) and _text_size(draw, cur[:cut], font)[0] <= max_width:
                    cut += 1
                cut = max(1, cut - 1)
                out.append(cur[:cut])
                cur = cur[cut:]
    if cur:
        out.append(cur)
    return out


def _wrap_cjk_chars(
    para: str,
    font: ImageFont.ImageFont,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> list[str]:
    """Greedy char wrap; prefer breaking after commas before mid-phrase cuts."""
    # Strong preference: break after commas / enumeration marks when wrapping.
    prefer_break_after = set(",，、")
    # Weaker soft breaks (spaces + sentence punctuation)
    soft_break_after = set(" ,.，、。.!?;:！？…·)~)]}」』")
    out: list[str] = []
    n = len(para)
    i = 0
    while i < n:
        # find largest j such that para[i:j] fits
        lo, hi = i + 1, n
        best = i + 1
        while lo <= hi:
            mid = (lo + hi) // 2
            tw, _ = _text_size(draw, para[i:mid], font)
            if tw <= max_width:
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1
        if best <= i:
            best = i + 1
        # Soft-back when not the last line: prefer commas (wide window), else other punctuation.
        if best < n and best - i > 4:
            soft = -1
            # Prefer comma-like breaks in a wider window (~last 60% of the chunk).
            prefer_start = i + max(1, int((best - i) * 0.4))
            for k in range(best - 1, prefer_start - 1, -1):
                if para[k] in prefer_break_after:
                    soft = k + 1
                    break
            # Fall back to other punctuation / spaces in last ~30%.
            if soft < 0:
                window_start = i + max(1, int((best - i) * 0.7))
                for k in range(best - 1, window_start - 1, -1):
                    if para[k] in soft_break_after or para[k].isspace():
                        soft = k + 1
                        break
            if soft > i:
                best = soft
        chunk = para[i:best].rstrip()
        if chunk:
            out.append(chunk)
        elif para[i:best]:
            out.append(para[i:best])
        i = best
        while i < n and para[i] == " ":
            i += 1
    return out or [""]


def _block_height(lines: list[str], font: ImageFont.ImageFont, line_gap: int, draw: ImageDraw.ImageDraw | None = None) -> int:
    if not lines:
        return 0
    if draw is None:
        draw = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    h = 0
    for i, line in enumerate(lines):
        if not line.strip():
            blank = int(getattr(font, "size", 26) * 0.4)
            h += blank
        else:
            _, th = _text_size(draw, line, font)
            h += th
        if i < len(lines) - 1:
            h += line_gap if line.strip() else 0
    return h


def _line_advance(font: ImageFont.ImageFont, line_gap: int, draw: ImageDraw.ImageDraw | None = None) -> int:
    _, th = _measure("가Ag", font, draw)
    return th + line_gap


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
    return base


def _split_units(source: str) -> list[dict[str, str]]:
    """Split source into section units at paragraph / numbered / bullet boundaries."""
    raw = source.strip()
    if not raw:
        raw = (
            "내용을 입력해 주세요.\n핵심 메시지를 간단히 정리합니다.\n"
            "실천 팁을 추가합니다.\n요약으로 마무리합니다.\n다음 액션을 안내합니다."
        )

    parts = re.split(r"\n\s*\n+|\n(?=\d+[\.\)]\s)|(?<=\n)(?=[•\-·]\s)", raw)
    parts = [p.strip() for p in parts if p and p.strip()]
    # Keep a single long blob as ONE unit; sentence splits happen in packing
    # so continuation slides share the same section title + "이어서".
    if not parts:
        parts = [raw]

    units: list[dict[str, str]] = []
    for chunk in parts:
        lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
        if not lines:
            continue
        title = lines[0][:40]
        body_lines = list(lines)
        first = lines[0]
        numbered = bool(re.match(r"^\d+[\.\)]\s", first))
        bulleted = bool(re.match(r"^[•\-·]\s", first))
        if numbered or (len(first) <= 28 and len(lines) > 1 and not bulleted):
            m = re.match(r"^(\d+[\.\)]\s*)?(.+)$", first)
            title = (m.group(2) if m else first)[:40]
            if len(lines) > 1 and (numbered or len(first) <= 24):
                body_lines = lines[1:]
        body = "\n".join(body_lines).strip() or chunk
        units.append({"title": title, "body": body, "raw": chunk})
    return units


def _sentence_pieces(text: str) -> list[str]:
    """Split body into sentence/bullet pieces for continuation boundaries."""
    pieces: list[str] = []
    for para in text.splitlines() or [""]:
        para = para.strip()
        if not para:
            continue
        if re.match(r"^[•\-·\d]", para):
            pieces.append(para)
            continue
        bits = re.split(r"(?<=[.!?。！？])\s+", para)
        for b in bits:
            b = b.strip()
            if b:
                pieces.append(b)
    return pieces or ([text.strip()] if text.strip() else [])


def _body_region_budget(
    title_lines: list[str],
    title_font: ImageFont.ImageFont,
    body_font: ImageFont.ImageFont,
    draw: ImageDraw.ImageDraw,
    text_top: int = BODY_TEXT_TOP,
) -> int:
    """Remaining pixel height for body lines inside the safe lower-third region."""
    title_h = _block_height(title_lines, title_font, TITLE_LINE_GAP, draw) if title_lines else 0
    used = title_h + (TITLE_BODY_GAP if title_lines else 0)
    available = TEXT_BOTTOM - text_top - used
    return max(available, _line_advance(body_font, BODY_LINE_GAP, draw))


def _pack_pieces_to_slides(
    section_title: str,
    pieces: list[str],
    title_font: ImageFont.ImageFont,
    body_font: ImageFont.ImageFont,
    draw: ImageDraw.ImageDraw,
    max_width: int = TEXT_MAX_WIDTH,
    text_top: int = BODY_TEXT_TOP,
) -> list[dict[str, str]]:
    """Pack sentence/bullet pieces into slides that fit the drawable region."""
    slides: list[dict[str, str]] = []
    remaining = list(pieces)
    cont = False

    while remaining:
        title = section_title
        marker = ""
        if cont:
            marker = CONTINUATION_MARK
            # keep hierarchy: same section title; subtle continuation hint in subtitle field
        title_lines = _wrap_to_width(title, title_font, max_width, draw)[:MAX_TITLE_LINES_BODY]
        budget = _body_region_budget(title_lines, title_font, body_font, draw, text_top=text_top)
        # leave a tiny safety pad
        budget = max(budget - 4, _line_advance(body_font, BODY_LINE_GAP, draw))

        taken: list[str] = []
        taken_lines: list[str] = []
        i = 0
        while i < len(remaining):
            piece = remaining[i]
            trial_text = "\n".join(taken + [piece])
            trial_lines = _wrap_to_width(trial_text, body_font, max_width, draw)
            h = _block_height(trial_lines, body_font, BODY_LINE_GAP, draw)
            if h <= budget:
                taken.append(piece)
                taken_lines = trial_lines
                i += 1
                continue
            # piece alone may exceed budget — split by wrapped lines at this boundary
            if not taken:
                single_lines = _wrap_to_width(piece, body_font, max_width, draw)
                fit: list[str] = []
                for ln in single_lines:
                    trial = fit + [ln]
                    if _block_height(trial, body_font, BODY_LINE_GAP, draw) <= budget:
                        fit.append(ln)
                    else:
                        break
                if not fit:
                    # force at least one line so we never infinite-loop
                    fit = single_lines[:1] or [piece[:20]]
                # Rejoin fitted lines as body; leftover lines become a new piece.
                # i must stay 0 so remaining[i:] keeps the rebuilt leftover (not wipe it).
                taken_lines = fit
                leftover_lines = single_lines[len(fit) :]
                joiner = "" if _looks_cjk_heavy(piece) else " "
                rebuilt = ([joiner.join(leftover_lines)] if leftover_lines else []) + remaining[1:]
                remaining = rebuilt
                taken = ["\n".join(fit)]
                i = 0
                break
            break

        if not taken and not taken_lines:
            # safety
            taken = [remaining.pop(0)]
            taken_lines = _wrap_to_width(taken[0], body_font, max_width, draw)
            remaining = remaining  # already popped
        else:
            remaining = remaining[i:]

        body_text = "\n".join(taken).strip()
        slides.append(
            {
                "role": "body",
                "title": title,
                "body": body_text,
                "continuation": "1" if cont else "",
                "marker": marker,
            }
        )
        cont = True
        if not remaining:
            break
    return slides


def _summarize_leftover(units_text: list[str], max_chars: int = 180) -> str:
    """Last-resort clear summary text — never silent mid-sentence drop."""
    joined = " ".join(t.strip() for t in units_text if t.strip())
    joined = re.sub(r"\s+", " ", joined).strip()
    if len(joined) <= max_chars:
        return joined
    # cut at sentence or space
    cut = joined[: max_chars - 1]
    for sep in ["。", ".", "!", "?", " "]:
        pos = cut.rfind(sep)
        if pos >= max_chars // 2:
            cut = cut[: pos + (0 if sep == " " else 1)]
            break
    return cut.rstrip() + "…"


def _split_source(source: str, max_slides: int = 8, min_slides: int = 5) -> list[dict[str, str]]:
    """Measure-aware split: fit real lower-third region; continue at sentence/bullet boundaries."""
    draw = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    title_font = _font(38, "semibold")
    body_font = _font(26, "regular")

    # Prefer quality pagination: use up to max_slides-2 body slots (cover+cta reserved).
    # min_slides only influences gentle filler later in build_slide_plan.
    body_budget = max(max_slides - 2, 1)  # typically 6

    units = _split_units(source)
    # Expand each unit into one or more fitted slides
    expanded: list[dict[str, str]] = []
    for u in units:
        pieces = _sentence_pieces(u["body"])
        packed = _pack_pieces_to_slides(
            u["title"], pieces, title_font, body_font, draw
        )
        expanded.extend(packed)

    if not expanded:
        expanded = [{"role": "body", "title": "핵심 포인트", "body": source.strip() or "내용을 입력해 주세요.", "continuation": "", "marker": ""}]

    if len(expanded) <= body_budget:
        # Prefer filling toward min body count only with short filler if truly sparse —
        # do NOT invent fake content beyond a gentle pad in build_slide_plan.
        return expanded

    # Too many body slides: keep first (body_budget - 1) as-is, merge rest into 요약 slide.
    keep_n = max(body_budget - 1, 1)
    head = expanded[:keep_n]
    tail = expanded[keep_n:]
    leftover_bits = [f"{t['title']}: {t['body']}" if t.get("title") else t["body"] for t in tail]
    summary = _summarize_leftover(leftover_bits, max_chars=220)
    # Ensure summary itself fits one slide
    summary_slides = _pack_pieces_to_slides(
        SUMMARY_TITLE, _sentence_pieces(summary), title_font, body_font, draw
    )
    # Only one summary slide (further trim if needed)
    if summary_slides:
        summary_slides = summary_slides[:1]
        summary_slides[0]["title"] = SUMMARY_TITLE
        summary_slides[0]["continuation"] = ""
        summary_slides[0]["marker"] = ""
    result = head + summary_slides
    return result[:body_budget]


def build_slide_plan(
    topic: str,
    audience: str,
    source: str,
    style_id: str,
    profile_name: str = "",
) -> list[dict[str, Any]]:
    """5~8장 슬라이드 플랜 — cover + measured body continuations + CTA."""
    style = STYLES.get(style_id, STYLES["style.clean"])
    bodies = _split_source(source, max_slides=MAX_TOTAL_SLIDES, min_slides=MIN_TOTAL_SLIDES)
    hook = cover_hook(topic, audience)
    cta = cta_copy(audience, topic)

    plan: list[dict[str, Any]] = []
    plan.append(
        {
            "role": "cover",
            "title": hook,
            "subtitle": topic,
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
                "continuation": b.get("continuation", ""),
                "marker": b.get("marker", ""),
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

    while len(plan) < MIN_TOTAL_SLIDES:
        plan.insert(
            -1,
            {
                "role": "body",
                "title": "핵심 포인트",
                "body": "핵심 내용을 한 줄로 정리해 전달합니다.\n독자가 바로 이해할 수 있게 짧게 씁니다.",
                "continuation": "",
                "marker": "",
                "style": style,
                "style_id": style_id,
                "topic": topic,
                "audience": audience,
            },
        )
    if len(plan) > MAX_TOTAL_SLIDES:
        # Keep cover, as many bodies as fit, CTA — leftover already summarized in _split_source
        keep_body = MAX_TOTAL_SLIDES - 2
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
    max_lines: int = 20,
    bottom: int = TEXT_BOTTOM,
) -> int:
    """Draw centered lines; never paint below the safe bottom edge."""
    y = start_y
    drawn = 0
    for line in lines:
        if drawn >= max_lines:
            break
        if not line.strip():
            blank = int(font.size * 0.4) if hasattr(font, "size") else 16
            if y + blank > bottom:
                break
            y += blank
            drawn += 1
            continue
        tw, th = _text_size(draw, line, font)
        if y + th > bottom:
            break
        x = (SIZE - tw) // 2
        if shadow:
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=fill)
        y += th + line_gap
        drawn += 1
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

        # Large hook in lower third, center-aligned (metric wrap).
        # Cover-only: hard-split after .。!?！？ and ,，、 before width wrap.
        y = BODY_TEXT_TOP
        hook_segments = _hard_split_cover_hook(str(slide.get("title", "")))
        hook_lines: list[str] = []
        for seg in hook_segments:
            hook_lines.extend(_wrap_to_width(seg, font_hook, TEXT_MAX_WIDTH, draw))
        hook_lines = hook_lines[:3]
        y = _draw_centered_block(
            draw, hook_lines, y, font_hook, (255, 255, 255), line_gap=14, max_lines=3
        )
        y += 8
        # topic as soft subtitle (not bland "X을 위한 카드뉴스")
        for line in _wrap_to_width(slide.get("subtitle", ""), font_sub, TEXT_MAX_WIDTH, draw)[:2]:
            if y + _measure(line, font_sub, draw)[1] > TEXT_BOTTOM:
                break
            y = _draw_centered(draw, line, y, font_sub, (230, 235, 245))
        if slide.get("body"):
            y += 10
            _draw_centered(draw, str(slide["body"]), y, font_meta, (200, 210, 225), shadow=False)
        draw.rectangle([0, SIZE - 10, SIZE, SIZE], fill=style["accent"])
        return img

    # Body / CTA — NO glass card. Lower-third, center-aligned (Instagram story).
    y = BODY_TEXT_TOP if role == "body" else CTA_TEXT_TOP

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

        title_lines = _wrap_to_width(slide.get("title", ""), font_title, TEXT_MAX_WIDTH, draw)[:3]
        y = _draw_centered_block(
            draw, title_lines, y, font_title, (255, 255, 255), line_gap=12, max_lines=3
        )
        y += 10
        sub_lines = _wrap_to_width(slide.get("subtitle", ""), font_sub, TEXT_MAX_WIDTH, draw)[:3]
        y = _draw_centered_block(
            draw, sub_lines, y, font_sub, (235, 240, 250), line_gap=8, max_lines=3
        )
        y += 16
        body_lines = _wrap_to_width(slide.get("body", ""), font_body, TEXT_MAX_WIDTH, draw)[:4]
        _draw_centered_block(
            draw, body_lines, y, font_body, (210, 218, 230), line_gap=8, max_lines=4
        )
    else:
        # small style chip centered near mid-upper of text block
        # Continuation slides reuse the chip for a subtle "이어서" marker (no extra vertical space).
        is_cont = bool(slide.get("continuation") or slide.get("marker") == CONTINUATION_MARK)
        style_name = STYLES.get(slide.get("style_id", ""), {}).get("name", "GUIDE")
        chip = CONTINUATION_MARK if is_cont else style_name.upper()[:18]
        tw, th = _text_size(draw, chip, font_label)
        pad_x, pad_y = 16, 8
        chip_w = tw + pad_x * 2
        chip_x = (SIZE - chip_w) // 2
        chip_y = y - CHIP_ABOVE
        draw.rounded_rectangle(
            (chip_x, chip_y, chip_x + chip_w, chip_y + th + pad_y * 2),
            radius=(th + pad_y * 2) // 2,
            fill=style["accent2"],
        )
        draw.text((chip_x + pad_x, chip_y + pad_y - 2), chip, font=font_label, fill=(255, 255, 255))

        title = str(slide.get("title", ""))[:40]
        title_lines = _wrap_to_width(title, font_title, TEXT_MAX_WIDTH, draw)[:MAX_TITLE_LINES_BODY]
        y = _draw_centered_block(
            draw,
            title_lines,
            y,
            font_title,
            (255, 255, 255),
            line_gap=TITLE_LINE_GAP,
            max_lines=MAX_TITLE_LINES_BODY,
        )
        y += TITLE_BODY_GAP
        body = str(slide.get("body", ""))
        body_text = body
        if body.startswith(title) and "\n" in body:
            body_text = body.split("\n", 1)[-1].strip() or body
        use_bullet = slide.get("style_id") == "style.bold"
        raw_lines = _wrap_to_width(body_text, font_body, TEXT_MAX_WIDTH, draw)
        if use_bullet:
            raw_lines = [
                ("•  " + ln if ln.strip() and not ln.lstrip().startswith("•") else ln)
                for ln in raw_lines
            ]
        _draw_centered_block(
            draw,
            raw_lines,
            y,
            font_body,
            (235, 240, 248),
            line_gap=BODY_LINE_GAP,
            max_lines=MAX_BODY_LINES_SOFT,
            bottom=TEXT_BOTTOM,
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

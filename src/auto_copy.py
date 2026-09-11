"""Template-based card copy from news + topic + settings (no paid LLM)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from .concepts import cta_from_pack, cover_hook_from_pack, normalize_concept_id
from .news_fetch import NewsItem, build_search_query, fetch_google_news

# Deterministic pick without importing renderer internals twice
def _pick(templates: list[str], seed: str) -> str:
    if not templates:
        return ""
    h = 0
    for ch in seed:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return templates[h % len(templates)]


_HOOK_INTROS = [
    "요즘 '{topic}' 관련해서 이런 이야기들이 나오고 있어요.",
    "'{topic}' — 지금 사람들이 주목하는 소식만 골랐어요.",
    "짧게 보는 '{topic}' 최신 흐름",
    "{audience}이라면 알아두면 좋은 '{topic}' 소식",
]

_BULLET_TITLES = [
    "지금 뜨는 소식",
    "핵심만 한 줄",
    "이것만 기억하세요",
    "현장에서 나온 이야기",
    "놓치기 쉬운 포인트",
]


@dataclass
class AutoCopyResult:
    topic: str
    audience: str
    concept_id: str
    query: str
    news_items: list[NewsItem]
    source: str
    cover_hint: str
    caption: str
    warnings: list[str]


def _shorten(text: str, max_len: int = 90) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if len(t) <= max_len:
        return t
    cut = t[: max_len - 1]
    for sep in ("。", ".", "!", "?", ",", " "):
        pos = cut.rfind(sep)
        if pos >= max_len // 2:
            cut = cut[: pos + (0 if sep == " " else 1)]
            break
    return cut.rstrip() + "…"


def _news_lang_for_concept(concept_id: str) -> str:
    """Most buyer concepts use Korean RSS; personal brand / custom may want both."""
    cid = normalize_concept_id(concept_id)
    if cid in ("personal_brand", "custom"):
        return "both"
    return "ko"


def apply_caption_template(template: str, topic: str, *, extra_blurb: str = "") -> str:
    """Fixed Instagram caption with light {주제} substitution."""
    raw = (template or "").strip()
    if not raw:
        raw = "[{주제}] 오늘의 카드뉴스\n\n#카드뉴스 #{주제}"
    out = raw.replace("{주제}", topic).replace("{topic}", topic)
    blurb = (extra_blurb or "").strip()
    if blurb and blurb not in out:
        out = out.rstrip() + "\n\n" + blurb
    return out.strip()


def build_source_from_news(
    *,
    topic: str,
    audience: str,
    concept_id: str,
    news_items: Sequence[NewsItem],
    always_include: str = "",
    closing_greeting: str = "",
) -> str:
    """
    Build numbered source text for generate_cardnews / _split_source.
    Uses concept-pack tone for hooks; merges always_include + closing_greeting.
    """
    cid = normalize_concept_id(concept_id)
    topic = (topic or "").strip() or "오늘 소식"
    audience = (audience or "").strip() or "입문자"

    try:
        hook = cover_hook_from_pack(cid, topic, audience, _pick)
    except Exception:
        hook = f"{topic}, 궁금증 여기서 풀어요"

    intro = _pick(_HOOK_INTROS, f"{cid}|{topic}|{audience}").format(
        topic=topic, audience=audience
    )

    sections: list[str] = []
    sections.append(f"1. {hook}\n{intro}")

    always = (always_include or "").strip()
    n = 2
    if always:
        sections.append(f"{n}. 꼭 알아두세요\n{_shorten(always, 160)}")
        n += 1

    items = list(news_items)[:5]
    if not items:
        sections.append(
            f"{n}. {topic} 한눈에\n"
            "관련 최신 뉴스를 찾지 못했어요. 주제만으로 핵심 포인트를 정리해 보세요.\n"
            f"• {topic}의 핵심 메시지\n"
            f"• {audience}에게 도움이 되는 한 가지\n"
            "• 오늘 바로 해볼 작은 행동"
        )
        n += 1
    else:
        for i, item in enumerate(items):
            title_label = _BULLET_TITLES[i % len(_BULLET_TITLES)]
            if i == 0:
                title_label = "지금 뜨는 소식"
            elif i == len(items) - 1 and len(items) > 1:
                title_label = "한 줄 더"
            head = _shorten(item.title, 70)
            body_bits: list[str] = [f"• {head}"]
            snip = _shorten(item.snippet, 100)
            if snip and snip not in head:
                body_bits.append(snip)
            if item.source:
                body_bits.append(f"(출처: {item.source})")
            sections.append(f"{n}. {title_label}\n" + "\n".join(body_bits))
            n += 1

    # Soft wrap-up body (closing_greeting is applied on CTA by generate_cardnews)
    try:
        cta = cta_from_pack(cid, audience)
        wrap_body = cta.get("subtitle") or "저장해 두고 필요할 때 다시 보세요."
    except Exception:
        wrap_body = "저장해 두고 필요할 때 다시 보세요."
    # Keep a light closing unit; greeting itself goes on last CTA slide.
    _ = closing_greeting  # accepted for API symmetry / future use
    sections.append(f"{n}. 한눈에 정리\n{wrap_body}\n오늘 소식, 핵심만 담았어요.")

    return "\n\n".join(sections)


def auto_build_card_inputs(
    *,
    topic: str,
    audience: str,
    concept_id: str,
    concept_label: str = "",
    caption_template: str = "",
    always_include: str = "",
    closing_greeting: str = "",
    news_limit: int = 5,
) -> AutoCopyResult:
    """
    Fetch news for topic and produce source + caption for generate_cardnews.
    """
    cid = normalize_concept_id(concept_id)
    topic = (topic or "").strip() or "오늘 소식"
    audience = (audience or "").strip() or "입문자"
    query = build_search_query(topic, concept_label)
    warnings: list[str] = []
    items: list[NewsItem] = []

    lang = _news_lang_for_concept(cid)
    try:
        items = fetch_google_news(query, limit=news_limit, lang=lang)
        if not items and lang == "ko":
            # fallback: topic-only English if Korean empty
            items = fetch_google_news(topic, limit=news_limit, lang="en")
            if items:
                warnings.append("한국어 뉴스가 적어 영문 소식을 일부 섞었어요.")
    except Exception as exc:
        warnings.append(f"뉴스 가져오기 실패: {exc}")
        items = []

    if not items:
        warnings.append("관련 뉴스를 찾지 못했어요. 주제 템플릿으로 카드를 만들어요.")

    source = build_source_from_news(
        topic=topic,
        audience=audience,
        concept_id=cid,
        news_items=items,
        always_include=always_include,
        closing_greeting=closing_greeting,
    )
    try:
        cover_hint = cover_hook_from_pack(cid, topic, audience, _pick)
    except Exception:
        cover_hint = topic

    caption = apply_caption_template(
        caption_template,
        topic,
        extra_blurb="",  # always_include already in cards; caption uses template only
    )
    # If template empty of topic hashtags, lightly enrich
    if topic and f"#{topic}" not in caption and "{주제}" not in (caption_template or ""):
        pass  # keep fixed caption as buyer wrote it

    return AutoCopyResult(
        topic=topic,
        audience=audience,
        concept_id=cid,
        query=query,
        news_items=items,
        source=source,
        cover_hint=cover_hint,
        caption=caption,
        warnings=warnings,
    )

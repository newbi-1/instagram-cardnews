"""Free Google News RSS fetch (no API key) — stdlib urllib + XML."""

from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Iterable

USER_AGENT = (
    "Mozilla/5.0 (compatible; InstagramCardnews/1.0; +https://github.com/newbi-1/instagram-cardnews)"
)
DEFAULT_TIMEOUT = 12.0
MAX_ITEMS = 8

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class NewsItem:
    title: str
    snippet: str
    link: str
    source: str
    published: str = ""


def _strip_html(text: str) -> str:
    text = html.unescape(text or "")
    text = _TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def _clean_title(title: str) -> tuple[str, str]:
    """Split 'Headline - Outlet' into (headline, outlet)."""
    raw = _strip_html(title)
    if " - " in raw:
        head, _, outlet = raw.rpartition(" - ")
        head, outlet = head.strip(), outlet.strip()
        if head and outlet and len(outlet) < 40:
            return head, outlet
    return raw, ""


def google_news_rss_url(
    query: str,
    *,
    hl: str = "ko",
    gl: str = "KR",
    ceid: str = "KR:ko",
) -> str:
    q = urllib.parse.quote_plus((query or "").strip())
    return (
        f"https://news.google.com/rss/search?q={q}"
        f"&hl={hl}&gl={gl}&ceid={urllib.parse.quote(ceid)}"
    )


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _child_text(el: ET.Element, names: Iterable[str]) -> str:
    want = set(names)
    for child in list(el):
        if _local_name(child.tag) in want:
            return (child.text or "").strip()
    return ""


def parse_rss_xml(xml_text: str, *, limit: int = MAX_ITEMS) -> list[NewsItem]:
    """Parse RSS/Atom-ish Google News XML into NewsItem list."""
    if not xml_text or not xml_text.strip():
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    items: list[NewsItem] = []
    # RSS: channel/item ; Atom: entry
    candidates = [
        el
        for el in root.iter()
        if _local_name(el.tag) in {"item", "entry"}
    ]
    for el in candidates:
        raw_title = _child_text(el, ("title",))
        title, outlet = _clean_title(raw_title)
        if not title:
            continue
        link = _child_text(el, ("link", "id"))
        # Atom <link href="..."/>
        if not link:
            for child in list(el):
                if _local_name(child.tag) == "link":
                    link = (child.attrib.get("href") or child.text or "").strip()
                    if link:
                        break
        desc = _strip_html(_child_text(el, ("description", "summary", "content")))
        # Google often duplicates title in description — trim if so
        snippet = desc
        if snippet.startswith(title):
            snippet = snippet[len(title) :].lstrip(" -–—|·:")
        source = outlet or _strip_html(_child_text(el, ("source",)))
        published = _child_text(el, ("pubDate", "published", "updated"))
        items.append(
            NewsItem(
                title=title[:160],
                snippet=snippet[:280],
                link=link,
                source=source[:80],
                published=published[:80],
            )
        )
        if len(items) >= limit:
            break
    return items


def fetch_rss_url(url: str, *, timeout: float = DEFAULT_TIMEOUT) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    for enc in ("utf-8", "utf-8-sig", "euc-kr", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def fetch_google_news(
    query: str,
    *,
    limit: int = 6,
    lang: str = "ko",
    timeout: float = DEFAULT_TIMEOUT,
) -> list[NewsItem]:
    """Fetch latest Google News RSS items for query. lang: 'ko' | 'en' | 'both'."""
    q = (query or "").strip()
    if not q:
        return []

    feeds: list[tuple[str, str, str]] = []
    if lang in ("ko", "both"):
        feeds.append(("ko", "KR", "KR:ko"))
    if lang in ("en", "both"):
        feeds.append(("en", "US", "US:en"))

    seen: set[str] = set()
    out: list[NewsItem] = []
    errors: list[str] = []

    for hl, gl, ceid in feeds:
        url = google_news_rss_url(q, hl=hl, gl=gl, ceid=ceid)
        try:
            xml_text = fetch_rss_url(url, timeout=timeout)
            for item in parse_rss_xml(xml_text, limit=limit * 2):
                key = item.title.casefold()
                if key in seen:
                    continue
                seen.add(key)
                out.append(item)
                if len(out) >= limit:
                    return out
        except Exception as exc:  # network / parse — caller shows friendly msg
            errors.append(f"{hl}:{exc}")

    if not out and errors:
        # Re-raise a compact error so UI can show it
        raise RuntimeError("; ".join(errors[:2]))
    return out


def build_search_query(topic: str, concept_label: str = "", extra: str = "") -> str:
    """Compose a buyer-friendly search query from topic + optional concept."""
    parts = [p.strip() for p in (topic, concept_label, extra) if p and str(p).strip()]
    # Avoid doubling if topic already contains concept label
    uniq: list[str] = []
    for p in parts:
        if not uniq or p not in uniq[0]:
            if all(p != u for u in uniq):
                uniq.append(p)
    return " ".join(uniq[:3]).strip()

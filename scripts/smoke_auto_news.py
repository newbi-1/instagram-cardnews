#!/usr/bin/env python3
"""Smoke: Google News RSS → auto_copy → generate_cardnews (optional network)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.auto_copy import auto_build_card_inputs, build_source_from_news
from src.news_fetch import NewsItem, build_search_query, parse_rss_xml
from src.profiles import ensure_demo_profile, outputs_dir
from src.renderer import generate_cardnews


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Google News</title>
<item>
  <title>카페 신메뉴 봄 시즌 라떼 출시 - 예시뉴스</title>
  <link>https://example.com/1</link>
  <description>고소한 시그니처 라떼가 새로 나왔다는 소식입니다.</description>
  <source>예시뉴스</source>
</item>
<item>
  <title>직장인 오후에 찾는 카페 트렌드 - 데일리</title>
  <link>https://example.com/2</link>
  <description>바쁜 오후에 부담 없는 한 잔이 인기입니다.</description>
</item>
</channel></rss>
"""


def main() -> int:
    ensure_demo_profile()
    items = parse_rss_xml(SAMPLE_RSS, limit=5)
    assert len(items) >= 2, items
    assert "카페 신메뉴" in items[0].title

    q = build_search_query("신메뉴", "카페")
    assert "신메뉴" in q

    source = build_source_from_news(
        topic="신메뉴",
        audience="직장인",
        concept_id="cafe",
        news_items=items,
        always_include="매일 10–22시 영업",
        closing_greeting="오늘도 반가워요",
    )
    assert "매일 10–22시" in source
    assert "지금 뜨는 소식" in source or "핵심" in source

    # Offline path through auto_build with mocked empty network is hard;
    # use direct generate from crafted source.
    out = outputs_dir("demo")
    paths = generate_cardnews(
        topic="신메뉴",
        audience="직장인",
        source=source,
        style_id="style.clean",
        out_dir=out,
        profile_name="웹",
        run_id="smoke_auto",
        concept_id="cafe",
        closing_greeting="오늘도 반가워요",
    )
    print(f"generated {len(paths)} slides")
    for p in paths:
        assert p.exists() and p.stat().st_size > 1000, p
        print(p)

    # Live RSS (best-effort; skip soft-fail)
    try:
        live = auto_build_card_inputs(
            topic="카페",
            audience="직장인",
            concept_id="cafe",
            concept_label="카페",
            caption_template="[{주제}] 테스트",
            always_include="고정문구",
            closing_greeting="감사합니다",
            news_limit=3,
        )
        print(f"live query={live.query!r} items={len(live.news_items)} warnings={live.warnings}")
        print("caption:", live.caption)
    except Exception as exc:
        print("live fetch skipped/failed:", exc)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""비대화형 스모크: 미리보기 PNG 1세트 생성."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.profiles import ensure_demo_profile, outputs_dir
from src.renderer import generate_cardnews

SAMPLE = """1. 신메뉴 출시 안내
고소한 시그니처 라떼를 새롭게 선보입니다.

2. 왜 이 메뉴인가
바쁜 오후에도 부담 없이 즐기는 한 잔을 목표로 했습니다.

3. 추천 대상
직장인 티타임, 자취생 주말 브런치에 잘 맞아요.

4. 주문 팁
아이스로 시키면 더 산뜻합니다. 샷 추가는 취향껏!

5. 이벤트
이번 주 방문 시 스티커 증정. 5장 모으면 음료 쿠폰.
"""


def main() -> int:
    ensure_demo_profile()
    out = outputs_dir("demo")
    paths = generate_cardnews(
        topic="신메뉴",
        audience="직장인",
        source=SAMPLE,
        style_id="style.clean",
        out_dir=out,
        profile_name="데모 카페",
        run_id="smoke_demo",
    )
    print(f"generated {len(paths)} slides")
    for p in paths:
        print(p)
        assert p.exists() and p.stat().st_size > 1000, p
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

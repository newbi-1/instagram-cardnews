#!/usr/bin/env python3
"""비대화형 스모크: 미리보기 PNG 세트 생성 (기본 + 긴 본문 이어쓰기)."""

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

# One long Korean section (no blank-line unit splits) so measure-aware packing
# produces multiple continuation ("이어서") body slides.
LONG_SAMPLE = """시그니처 라떼 완벽 가이드
바쁜 오후의 작은 보상을 위해 준비한 시그니처 라떼는 원두의 고소함과 우유의 부드러움을 균형 있게 맞춘 메뉴입니다. 첫 모금에서는 견과류처럼 고소한 향이 먼저 느껴지고, 이어서 은은한 단맛이 입안을 감싸며 마무리는 깔끔하게 떨어지도록 설계했습니다. 직장인 티타임에는 부담 없는 용량으로, 자취생의 주말 브런치에는 디저트와 함께 즐기기 좋은 농도로 맞춰 두었습니다. 원두는 중배전으로 로스팅해 쓴맛을 누르고 고소함을 살렸습니다. 추출은 18g 기준으로 25~28초를 목표로 하며, 크레마가 너무 두껍지 않게 유지하는 것이 포인트입니다. 우유는 60~65도에서 스티밍해 미세한 폼을 만들고, 라떼 아트를 올려도 무너지지 않을 정도의 점도를 유지합니다. 아이스로 주문할 때는 샷을 먼저 내리고 얼음과 우유 비율을 1:2로 맞추면 물처럼 희석되지 않고 산뜻하게 즐길 수 있습니다. 샷 추가는 취향에 따라 선택하세요. 단맛을 더 원하면 바닐라 시럽 한 펌프, 고소함을 강조하고 싶다면 헤이즐넛을 추천합니다. 카페인이 부담되면 디카페인 원두로 동일 레시피를 적용할 수 있고, 비건 고객을 위해서는 오트밀크 치환이 가능합니다. 오트밀크는 일반 우유보다 단맛이 강하므로 시럽은 반 펌프로 줄이는 편이 균형이 좋습니다. 이번 주 방문 고객에게는 스탬프 스티커를 드립니다. 다섯 장을 모으면 아메리카노 쿠폰으로 교환할 수 있으며, 시그니처 라떼를 포함해 어떤 음료에도 적용됩니다. 친구와 함께 오시면 두 번째 음료를 할인받을 수 있는 페어 혜택도 함께 진행 중이니, 저장해 두고 방문 전에 확인해 주세요. 매장 혼잡 시간대는 오후 1시부터 3시이므로, 여유 있는 좌석을 원하시면 오전이나 늦은 오후를 추천드립니다. 마지막으로, 테이크아웃 잔은 친환경 소재로 교체했고 뚜껑과 홀더는 요청 시에만 제공합니다. 매장에서 드실 때는 머그잔을 기본으로 드리며, 개인 텀블러 지참 시 200원 할인이 적용됩니다. 알레르기 정보는 카운터에 비치된 안내문을 확인해 주시고, 궁금한 점은 언제든 바리스타에게 물어보시면 친절히 안내해 드리겠습니다. 오늘도 작은 여유가 필요한 순간, 시그니처 라떼 한 잔으로 오후를 채워 보세요.
"""


def _run(run_id: str, source: str) -> list[Path]:
    out = outputs_dir("demo")
    paths = generate_cardnews(
        topic="신메뉴",
        audience="직장인",
        source=source,
        style_id="style.clean",
        out_dir=out,
        profile_name="데모 카페",
        run_id=run_id,
    )
    print(f"[{run_id}] generated {len(paths)} slides")
    for p in paths:
        print(p)
        assert p.exists() and p.stat().st_size > 1000, p
    return paths


def main() -> int:
    ensure_demo_profile()
    _run("smoke_demo", SAMPLE)
    long_paths = _run("smoke_long", LONG_SAMPLE)
    assert len(long_paths) >= 5, f"expected >=5 slides, got {len(long_paths)}"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

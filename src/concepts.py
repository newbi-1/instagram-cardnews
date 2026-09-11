"""Industry / concept packs — buyers pick a concept first (not cafe-only)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .presets import AUDIENCES, TOPICS

# Canonical concept ids (English snake_case for storage).
CONCEPT_IDS = [
    "cafe",
    "shopping",
    "academy",
    "clinic",
    "real_estate",
    "restaurant",
    "personal_brand",
    "custom",
]

# Korean UI labels (same order as CONCEPT_IDS).
CONCEPT_LABELS: dict[str, str] = {
    "cafe": "카페",
    "shopping": "쇼핑몰",
    "academy": "학원",
    "clinic": "병원/클리닉",
    "real_estate": "부동산",
    "restaurant": "식당",
    "personal_brand": "개인브랜딩",
    "custom": "직접 입력",
}

DEFAULT_CONCEPT_ID = "cafe"


def _pack(
    *,
    topic_chips: list[str],
    audience_chips: list[str],
    photo_pools: dict[str, list[str]],
    default_photo_pool: list[str],
    cover_hooks_pair: dict[tuple[str, str], str] | None = None,
    cover_hooks_topic: dict[str, list[str]] | None = None,
    cover_hooks_audience: dict[str, list[str]] | None = None,
    generic_hooks: list[str] | None = None,
    cta_by_audience: dict[str, dict[str, str]] | None = None,
    cta_default: dict[str, str] | None = None,
    sample_source: str = "",
) -> dict[str, Any]:
    return {
        "topic_chips": topic_chips,
        "audience_chips": audience_chips,
        "photo_pools": photo_pools,
        "default_photo_pool": default_photo_pool,
        "cover_hooks_pair": cover_hooks_pair or {},
        "cover_hooks_topic": cover_hooks_topic or {},
        "cover_hooks_audience": cover_hooks_audience or {},
        "generic_hooks": generic_hooks
        or [
            "{audience}이라면 한번 보세요",
            "{topic}, 궁금증 여기서 풀어요",
            "스크롤 멈추게 하는 {topic}",
            "저장해 두고 나중에 보세요",
        ],
        "cta_by_audience": cta_by_audience or {},
        "cta_default": cta_default
        or {
            "title": "저장하고 공유해 보세요",
            "subtitle": "필요할 때 다시 꺼내볼 수 있어요",
            "body": "도움이 됐다면 좋아요, 생각은 댓글로 남겨 주세요. 저장해 두고, 팔로우하면 다음 카드도 받아볼 수 있어요",
        },
        "sample_source": sample_source,
    }


# Shared soft CTA tones (concept-specific overlays merge on top).
_CTA_SOFT = {
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


CONCEPT_PACKS: dict[str, dict[str, Any]] = {
    "cafe": _pack(
        topic_chips=["신메뉴", "후기", "이벤트", "꿀팁", "공지", "할인/프로모"],
        audience_chips=["직장인", "자취생", "직장맘", "동네 주민", "학생", "사장님"],
        photo_pools={
            "신메뉴": ["latte", "coffee", "cafe", "espresso", "cappuccino", "barista", "mug", "pastry"],
            "후기": ["happy", "smile", "cafe", "friends", "customer", "portrait", "coffee", "joy"],
            "이벤트": ["party", "cafe", "balloon", "celebration", "dessert", "crowd", "lights", "pastry"],
            "꿀팁": ["barista", "espresso", "latteart", "notebook", "cafe", "mug", "beans", "brew"],
            "공지": ["cafe", "sign", "counter", "menu", "shop", "door", "window", "interior"],
            "할인/프로모": ["coupon", "coffee", "gift", "mug", "cafe", "pastry", "bag", "sale"],
        },
        default_photo_pool=["cafe", "coffee", "latte", "pastry", "interior", "mug", "barista", "cozy"],
        cover_hooks_pair={
            ("신메뉴", "직장인"): "오후 3시, 이 한 잔이면 달라져요",
            ("신메뉴", "자취생"): "집에서 카페 기분, 첫 모금에 반해요",
            ("신메뉴", "직장맘"): "잠깐의 여유, 이 메뉴로 채워보세요",
            ("이벤트", "동네 주민"): "이번 주만, 놓치면 아쉬운 혜택",
            ("할인/프로모", "사장님"): "손님 발길 붙잡는 할인 포인트",
            ("꿀팁", "직장인"): "지금 바로 써먹는 카페 꿀팁",
        },
        cover_hooks_topic={
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
                "직접 마셔본 솔직 후기",
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
            "할인/프로모": [
                "혜택, 지금이 타이밍",
                "{audience} 지갑 사수 팁",
                "할인 포인트만 모아봤어요",
            ],
        },
        cover_hooks_audience={
            "직장맘": ["바쁜 하루, 이것만은 챙기세요", "육아·업무 사이 작은 여유"],
            "자취생": ["자취생 필수, 이것부터", "혼라이프가 편해지는 한 가지"],
            "사장님": ["손님 반응이 달라지는 포인트", "매출에 도움 되는 한 줄 요약"],
            "직장인": ["퇴근 전 3분이면 충분해요", "직장인이 저장하는 이유"],
            "동네 주민": ["우리 동네 소식, 핵심만", "근처라면 꼭 보세요"],
            "학생": ["과제보다 먼저 볼 카드", "학생이 공감하는 포인트"],
        },
        cta_by_audience=deepcopy(_CTA_SOFT),
        sample_source=(
            "1. 오늘 신메뉴 출시\n"
            "고소하고 진한 시그니처 라떼를 새롭게 선보입니다.\n\n"
            "2. 왜 이 메뉴인가\n"
            "바쁜 오후에 부담 없이 즐길 수 있는 한 잔을 목표로 했습니다.\n\n"
            "3. 추천 타겟\n"
            "직장인 오후 티타임, 자취생 주말 브런치에 잘 맞아요.\n\n"
            "4. 주문 팁\n"
            "아이스로 시키면 더 산뜻합니다. 샷 추가는 취향껏!\n\n"
            "5. 이벤트\n"
            "이번 주 방문 시 스티커 1장 증정. 5장 모으면 음료 쿠폰."
        ),
    ),
    "shopping": _pack(
        topic_chips=["신메뉴", "후기", "이벤트", "할인/프로모", "사용법", "전후", "꿀팁"],
        audience_chips=["직장맘", "직장인", "자취생", "입문자", "학생", "동네 주민"],
        photo_pools={
            "신메뉴": ["product", "shopping", "unboxing", "fashion", "store", "display", "retail", "bag"],
            "후기": ["happy", "shopping", "customer", "smile", "lifestyle", "portrait", "bag", "joy"],
            "이벤트": ["sale", "shopping", "mall", "crowd", "lights", "gift", "store", "celebration"],
            "할인/프로모": ["sale", "shopping", "coupon", "gift", "bag", "mall", "retail", "price"],
            "사용법": ["unboxing", "product", "hands", "howto", "tutorial", "box", "gadget", "demo"],
            "전후": ["fashion", "mirror", "outfit", "style", "portrait", "studio", "closet", "look"],
            "꿀팁": ["shopping", "planner", "checklist", "notebook", "bag", "wallet", "style", "tips"],
        },
        default_photo_pool=["shopping", "store", "fashion", "bag", "product", "mall", "retail", "gift"],
        cover_hooks_pair={
            ("할인/프로모", "직장맘"): "장바구니 전에 볼 할인 포인트",
            ("후기", "입문자"): "써보니 달랐어요 — 솔직 후기",
            ("신메뉴", "직장인"): "오늘 올라온 신상, 먼저 보세요",
            ("전후", "입문자"): "전·후 차이, 사진으로 확인해 보세요",
        },
        cover_hooks_topic={
            "신메뉴": [
                "방금 입고된 {topic}",
                "{audience}이 찜한 신상",
                "품절 전에 확인해 보세요",
            ],
            "할인/프로모": [
                "지금이 가장 싸요",
                "{audience} 지갑 사수 세일",
                "쿠폰·할인만 모아봤어요",
            ],
            "후기": [
                "구매 전 꼭 볼 솔직 후기",
                "{audience} 만족도가 높은 이유",
                "별점보다 생생한 사용감",
            ],
            "전후": [
                "착용 전·후, 눈으로 확인",
                "스타일 변화가 한눈에",
                "{audience}이 놀란 차이",
            ],
            "사용법": [
                "개봉부터 활용까지",
                "초보도 OK, 사용 가이드",
                "따라만 하면 되는 팁",
            ],
            "이벤트": [
                "오늘만 참여 가능",
                "{audience} 위한 쇼핑 혜택",
                "저장해 두고 응모하세요",
            ],
            "꿀팁": [
                "알뜰 쇼핑 꿀팁",
                "{audience}이 몰래 쓰는 팁",
                "실패 없이 고르는 법",
            ],
        },
        cover_hooks_audience={
            "직장맘": ["바쁜 쇼핑, 이것만 보면 끝", "맘 추천 아이템 정리"],
            "자취생": ["자취생 필수템, 이것부터", "가성비 쇼핑 체크리스트"],
            "입문자": ["처음 사도 실패 없는 가이드", "입문자 추천 픽"],
            "직장인": ["출퇴근룩에 바로 쓰는 팁", "직장인이 저장하는 신상"],
            "학생": ["학생 예산으로도 OK", "캠퍼스에서 돋보이는 픽"],
        },
        cta_by_audience={
            **deepcopy(_CTA_SOFT),
            "직장맘": {
                "title": "맘 단톡에도 공유해 보세요",
                "subtitle": "장보기 전에 다시 볼 수 있게, 저장해 두세요",
                "body": "도움이 됐다면 좋아요, 추천템은 댓글로 남겨 주세요. 팔로우하면 다음 세일 소식도 받아볼 수 있어요",
            },
            "직장인": {
                "title": "동료에게도 살짝 공유해요",
                "subtitle": "장바구니에 담기 전에, 저장해 두세요",
                "body": "유용했다면 좋아요, 구매 후기는 댓글로 남겨 주세요. 팔로우하면 신상·할인 카드도 이어져요",
            },
        },
        sample_source=(
            "1. 신상 입고 안내\n"
            "이번 주 가장 많이 문의 받은 아이템을 선보입니다.\n\n"
            "2. 왜 지금인가\n"
            "시즌 한정 컬러와 가성비 구성으로 준비했습니다.\n\n"
            "3. 추천 대상\n"
            "직장인 데일리룩, 자취생 필수템으로 좋아요.\n\n"
            "4. 구매 팁\n"
            "사이즈 가이드를 확인하고, 첫 구매 쿠폰을 적용하세요.\n\n"
            "5. 이벤트\n"
            "오늘 주문 시 무료 배송 + 사은품 증정."
        ),
    ),
    "academy": _pack(
        topic_chips=["꿀팁", "사용법", "공지", "후기", "이벤트", "혜택가이드", "전후"],
        audience_chips=["학부모", "학생", "입문자", "직장인", "직장맘", "사장님"],
        photo_pools={
            "꿀팁": ["study", "notebook", "desk", "books", "pen", "classroom", "laptop", "checklist"],
            "사용법": ["tutorial", "classroom", "whiteboard", "teacher", "books", "desk", "notes", "guide"],
            "공지": ["school", "bulletin", "classroom", "calendar", "desk", "notice", "board", "paper"],
            "후기": ["happy", "student", "graduation", "smile", "classroom", "portrait", "books", "joy"],
            "이벤트": ["school", "celebration", "students", "campus", "event", "balloon", "crowd", "stage"],
            "혜택가이드": ["scholarship", "checklist", "planner", "documents", "calendar", "notes", "folder", "pen"],
            "전후": ["study", "progress", "notebook", "chart", "desk", "books", "focus", "results"],
        },
        default_photo_pool=["study", "classroom", "books", "notebook", "desk", "student", "campus", "pen"],
        cover_hooks_pair={
            ("꿀팁", "학부모"): "아이 성적, 이렇게만 바꿔보세요",
            ("꿀팁", "학생"): "시험 전에 꼭 볼 공부 팁",
            ("공지", "학부모"): "꼭 알아야 할 학원 공지, 한눈에",
            ("사용법", "입문자"): "처음이어도 3분이면 따라와요",
            ("혜택가이드", "직장맘"): "바쁜 하루, 수강 혜택만 쏙쏙",
        },
        cover_hooks_topic={
            "꿀팁": [
                "{audience}이 몰래 쓰는 공부 팁",
                "알면 점수 오르는 {topic}",
                "오늘부터 바로 적용하세요",
            ],
            "사용법": [
                "따라만 하면 되는 학습법",
                "초보도 OK, 단계별 가이드",
                "복습이 쉬워지는 루틴",
            ],
            "공지": [
                "놓치면 아쉬운 학원 소식",
                "{audience}이 꼭 확인하세요",
                "핵심만 짧게 정리",
            ],
            "후기": [
                "수강생 솔직 후기",
                "{audience} 반응이 좋은 이유",
                "변화가 느껴진 순간",
            ],
            "전후": [
                "성적 전·후, 숫자로 확인",
                "학습 루틴이 바꾼 결과",
                "{audience}이 놀란 변화",
            ],
            "이벤트": [
                "이번 기수만 열린 기회",
                "{audience} 위한 수강 혜택",
                "저장해 두고 신청하세요",
            ],
            "혜택가이드": [
                "수강료·장학 혜택 한눈에",
                "{audience} 맞춤 혜택 가이드",
                "알아두면 이득인 안내",
            ],
        },
        cover_hooks_audience={
            "학부모": ["아이 위해 알아두면 좋은 정보", "학부모 공감 100%"],
            "학생": ["과제보다 먼저 볼 카드", "학생이 공감하는 포인트"],
            "입문자": ["처음이어도 어렵지 않아요", "입문자가 가장 먼저 볼 내용"],
            "직장인": ["퇴근 후 3분이면 충분해요", "직장인 자기계발 요약"],
            "직장맘": ["바쁜 하루, 이것만은 챙기세요", "육아·학습 사이 작은 팁"],
        },
        cta_by_audience={
            **deepcopy(_CTA_SOFT),
            "학부모": {
                "title": "학부모 단톡에도 공유해 보세요",
                "subtitle": "상담·신청 전에 다시 볼 수 있게, 저장해 두세요",
                "body": "공감되셨다면 좋아요, 경험은 댓글로 남겨 주세요. 팔로우하면 다음 학습 가이드도 받아볼 수 있어요",
            },
            "학생": {
                "title": "스터디 메이트에게도 공유해요",
                "subtitle": "시험 전에 다시 볼 수 있게, 저장해 두세요",
                "body": "도움이 됐다면 좋아요, 질문은 댓글로 남겨 주세요. 팔로우하면 다음 카드도 이어져요",
            },
        },
        sample_source=(
            "1. 이번 달 커리큘럼 안내\n"
            "기초부터 실전까지, 주 2회 집중 수업을 엽니다.\n\n"
            "2. 왜 이 과정인가\n"
            "혼자 공부할 때 막히는 지점을 먼저 점검합니다.\n\n"
            "3. 추천 대상\n"
            "학부모 상담용, 입문자·학생 자기주도 학습에 좋아요.\n\n"
            "4. 수강 팁\n"
            "첫 주는 복습 노트를 꼭 챙기세요. 질문 시간은 매 수업 끝!\n\n"
            "5. 혜택\n"
            "이번 기수 등록 시 교재비 지원 + 무료 진단 테스트."
        ),
    ),
    "clinic": _pack(
        topic_chips=["전후", "사용법", "후기", "공지", "꿀팁", "이벤트", "혜택가이드"],
        audience_chips=["직장맘", "직장인", "입문자", "학부모", "동네 주민", "자취생"],
        photo_pools={
            "전후": ["clinic", "skincare", "beauty", "wellness", "portrait", "mirror", "care", "glow"],
            "사용법": ["clinic", "hands", "care", "howto", "wellness", "treatment", "doctor", "guide"],
            "후기": ["happy", "smile", "patient", "clinic", "portrait", "wellness", "care", "joy"],
            "공지": ["clinic", "hospital", "reception", "waiting", "sign", "desk", "calendar", "office"],
            "꿀팁": ["wellness", "healthy", "lifestyle", "care", "water", "rest", "yoga", "checklist"],
            "이벤트": ["clinic", "care", "gift", "wellness", "calendar", "flower", "smile", "event"],
            "혜택가이드": ["checklist", "documents", "planner", "clinic", "notes", "folder", "pen", "calendar"],
        },
        default_photo_pool=["clinic", "wellness", "care", "health", "doctor", "skincare", "calm", "clean"],
        cover_hooks_pair={
            ("전후", "입문자"): "전·후 차이, 사진으로 확인해 보세요",
            ("사용법", "입문자"): "처음이어도 부담 없이 따라와요",
            ("후기", "직장맘"): "바쁜 일상 속, 회복이 느껴진 순간",
            ("공지", "동네 주민"): "우리 동네 클리닉 소식, 핵심만",
            ("꿀팁", "직장인"): "퇴근 후 3분 케어 루틴",
        },
        cover_hooks_topic={
            "전후": [
                "변화, 눈으로 확인하세요",
                "케어 전·후가 말해 주는 차이",
                "{audience}이 놀란 결과",
            ],
            "사용법": [
                "따라만 하면 되는 케어법",
                "초보도 OK, 단계별 안내",
                "오늘 바로 적용해 보세요",
            ],
            "후기": [
                "내원 후 솔직 후기",
                "{audience} 만족도가 높은 이유",
                "별점보다 생생한 이야기",
            ],
            "공지": [
                "놓치면 아쉬운 진료 안내",
                "{audience}이 꼭 확인하세요",
                "예약·운영, 핵심만 정리",
            ],
            "꿀팁": [
                "일상에서 바로 쓰는 케어 팁",
                "{audience}이 몰래 챙기는 습관",
                "알면 이득인 건강 팁",
            ],
            "이벤트": [
                "이번 달만 가능한 케어 혜택",
                "{audience} 위한 특별 안내",
                "저장해 두고 예약하세요",
            ],
            "혜택가이드": [
                "진료·패키지 혜택 한눈에",
                "{audience} 맞춤 혜택 가이드",
                "알아두면 이득인 안내",
            ],
        },
        cover_hooks_audience={
            "직장맘": ["바쁜 하루, 회복만은 챙기세요", "육아·업무 사이 작은 케어"],
            "직장인": ["퇴근 후 3분이면 충분해요", "직장인이 저장하는 루틴"],
            "입문자": ["처음이어도 어렵지 않아요", "입문자가 가장 먼저 볼 내용"],
            "동네 주민": ["우리 동네 클리닉 소식", "근처라면 꼭 보세요"],
            "학부모": ["가족 건강, 알아두면 좋은 정보", "학부모 공감 케어 팁"],
        },
        cta_by_audience={
            **deepcopy(_CTA_SOFT),
            "직장맘": {
                "title": "같은 맘 친구에게 전해 주세요",
                "subtitle": "예약 전에 다시 볼 수 있게, 저장해 두세요",
                "body": "공감되셨다면 좋아요, 경험은 댓글로 남겨 주세요. 팔로우하면 다음 케어 가이드도 받아볼 수 있어요",
            },
            "동네 주민": {
                "title": "이웃에게도 전해 주세요",
                "subtitle": "방문 전에 다시 볼 수 있게, 저장해 두세요",
                "body": "유익했다면 좋아요, 궁금한 점은 댓글로 남겨 주세요. 팔로우하면 다음 소식도 이어져요",
            },
        },
        sample_source=(
            "1. 이번 달 케어 프로그램\n"
            "일상 피로를 덜어 주는 맞춤 케어를 소개합니다.\n\n"
            "2. 왜 필요한가\n"
            "짧은 시간이라도 회복 루틴이 쌓이면 컨디션이 달라집니다.\n\n"
            "3. 추천 대상\n"
            "직장인·직장맘, 입문자도 부담 없이 시작할 수 있어요.\n\n"
            "4. 방문 팁\n"
            "첫 상담 때 생활 패턴을 말씀해 주시면 더 정확합니다.\n\n"
            "5. 안내\n"
            "이번 주 예약 시 상담비 혜택. 자세한 일정은 공지를 확인하세요."
        ),
    ),
    "real_estate": _pack(
        topic_chips=["공지", "꿀팁", "후기", "이벤트", "혜택가이드", "사용법", "전후"],
        audience_chips=["직장인", "사장님", "직장맘", "자취생", "동네 주민", "학부모"],
        photo_pools={
            "공지": ["house", "apartment", "keys", "building", "office", "sign", "city", "door"],
            "꿀팁": ["home", "interior", "checklist", "keys", "apartment", "planner", "documents", "desk"],
            "후기": ["happy", "family", "home", "moving", "keys", "smile", "livingroom", "joy"],
            "이벤트": ["openhouse", "house", "balloon", "keys", "building", "crowd", "sign", "event"],
            "혜택가이드": ["documents", "checklist", "contract", "keys", "folder", "pen", "calendar", "office"],
            "사용법": ["keys", "tour", "home", "howto", "checklist", "apartment", "guide", "door"],
            "전후": ["renovation", "interior", "beforeafter", "home", "livingroom", "design", "house", "style"],
        },
        default_photo_pool=["house", "apartment", "keys", "interior", "building", "home", "city", "door"],
        cover_hooks_pair={
            ("꿀팁", "직장인"): "계약 전 꼭 볼 부동산 팁",
            ("공지", "동네 주민"): "우리 동네 매물 소식, 핵심만",
            ("후기", "직장맘"): "이사 후기, 솔직하게 정리했어요",
            ("혜택가이드", "사장님"): "중개·대출 혜택만 쏙쏙",
            ("전후", "입문자"): "리모델링 전·후, 눈으로 확인",
        },
        cover_hooks_topic={
            "공지": [
                "놓치면 아쉬운 매물 소식",
                "{audience}이 꼭 확인하세요",
                "핵심만 짧게 정리",
            ],
            "꿀팁": [
                "계약 전에 아는 {topic}",
                "{audience}이 손해 보지 않는 팁",
                "오늘 바로 체크리스트",
            ],
            "후기": [
                "실제 이사·계약 후기",
                "{audience} 반응이 좋은 이유",
                "현장감 있는 이야기",
            ],
            "이벤트": [
                "오픈하우스·특별 혜택",
                "{audience} 위한 방문 기회",
                "저장해 두고 예약하세요",
            ],
            "혜택가이드": [
                "중개·대출 혜택 한눈에",
                "{audience} 맞춤 혜택 가이드",
                "알아두면 이득인 안내",
            ],
            "사용법": [
                "매물 보는 법, 단계별",
                "초보도 OK, 체크 가이드",
                "실수 없이 보는 포인트",
            ],
            "전후": [
                "공간 변화, 눈으로 확인",
                "리모델링 전·후 차이",
                "{audience}이 놀란 결과",
            ],
        },
        cover_hooks_audience={
            "직장인": ["출퇴근 동선부터 보세요", "직장인이 저장하는 매물 팁"],
            "사장님": ["상가·투자 포인트 요약", "사장님이 놓치지 않는 체크"],
            "직장맘": ["아이 통학·생활권 체크", "가족이 편한 집 고르는 법"],
            "자취생": ["자취생 필수, 이것부터", "월세·옵션 한눈에"],
            "동네 주민": ["우리 동네 매물 소식", "근처라면 꼭 보세요"],
        },
        cta_by_audience={
            **deepcopy(_CTA_SOFT),
            "사장님": {
                "title": "사장님 커뮤니티에 공유해 보세요",
                "subtitle": "상담·계약 전에 다시 볼 수 있게, 저장해 두세요",
                "body": "도움이 됐다면 좋아요, 현장 후기는 댓글로 남겨 주세요. 팔로우하면 매물·혜택 소식도 이어져요",
            },
            "직장인": {
                "title": "동료에게도 살짝 공유해요",
                "subtitle": "임장 전에 다시 볼 수 있게, 저장해 두세요",
                "body": "유용했다면 좋아요, 질문은 댓글로 남겨 주세요. 팔로우하면 다음 가이드도 받아볼 수 있어요",
            },
        },
        sample_source=(
            "1. 이번 주 추천 매물\n"
            "역세권·생활권이 균형 잡힌 매물을 소개합니다.\n\n"
            "2. 왜 이 매물인가\n"
            "출퇴근·학군·편의시설을 기준으로 골랐습니다.\n\n"
            "3. 추천 대상\n"
            "직장인 신혼, 자취 이사, 투자 검토에 참고하세요.\n\n"
            "4. 임장 팁\n"
            "낮·저녁 소음과 주차부터 체크하세요.\n\n"
            "5. 안내\n"
            "주말 오픈하우스 예약 가능. 상담은 프로필 링크 참고."
        ),
    ),
    "restaurant": _pack(
        topic_chips=["신메뉴", "후기", "이벤트", "꿀팁", "공지", "할인/프로모", "전후"],
        audience_chips=["동네 주민", "직장인", "자취생", "직장맘", "학생", "사장님"],
        photo_pools={
            "신메뉴": ["food", "restaurant", "dish", "gourmet", "plate", "chef", "dinner", "cuisine"],
            "후기": ["happy", "dining", "friends", "food", "restaurant", "smile", "meal", "joy"],
            "이벤트": ["restaurant", "party", "table", "celebration", "wine", "crowd", "lights", "dinner"],
            "꿀팁": ["menu", "restaurant", "chef", "kitchen", "plate", "tips", "fork", "dining"],
            "공지": ["restaurant", "sign", "door", "menu", "table", "interior", "window", "counter"],
            "할인/프로모": ["coupon", "food", "restaurant", "gift", "meal", "sale", "table", "dining"],
            "전후": ["plating", "food", "chef", "kitchen", "dish", "style", "plate", "gourmet"],
        },
        default_photo_pool=["food", "restaurant", "dish", "dining", "chef", "plate", "meal", "table"],
        cover_hooks_pair={
            ("신메뉴", "직장인"): "점심 고민 끝, 이 메뉴면 돼요",
            ("신메뉴", "자취생"): "오늘 외식, 이 한 접시로 충분해요",
            ("이벤트", "동네 주민"): "이번 주만, 놓치면 아쉬운 혜택",
            ("후기", "직장맘"): "가족 식사, 반응이 좋았던 이유",
            ("꿀팁", "사장님"): "손님 만족을 올리는 한 줄 팁",
        },
        cover_hooks_topic={
            "신메뉴": [
                "{audience}이 먼저 찾는 그 맛",
                "새로 나왔어요 — 궁금하지 않나요?",
                "첫술에 반하는 {topic}",
            ],
            "후기": [
                "직접 먹어본 솔직 후기",
                "{audience} 반응이 좋은 이유",
                "별점보다 생생한 맛 이야기",
            ],
            "이벤트": [
                "지금만 가능한 식사 혜택",
                "{audience} 위한 깜짝 메뉴",
                "저장해 두고 예약하세요",
            ],
            "꿀팁": [
                "{audience}이 몰래 쓰는 주문 팁",
                "알면 더 맛있는 포인트",
                "오늘 바로 써먹는 팁",
            ],
            "공지": [
                "놓치면 아쉬운 식당 소식",
                "{audience}이 꼭 확인하세요",
                "영업·예약, 핵심만 정리",
            ],
            "할인/프로모": [
                "혜택, 지금이 타이밍",
                "{audience} 지갑 사수 팁",
                "할인·세트만 모아봤어요",
            ],
            "전후": [
                "플레이팅 전·후 차이",
                "비주얼이 말해 주는 완성도",
                "{audience}이 놀란 한 접시",
            ],
        },
        cover_hooks_audience={
            "동네 주민": ["우리 동네 맛집 소식", "근처라면 꼭 보세요"],
            "직장인": ["점심·회식 고민 끝", "직장인이 저장하는 메뉴"],
            "자취생": ["자취생 외식 추천", "혼밥도 편한 한 끼"],
            "직장맘": ["가족 식사, 이것만 보면", "아이와 가기 좋은 포인트"],
            "학생": ["학생 예산으로도 OK", "친구랑 가기 좋은 메뉴"],
            "사장님": ["손님 반응이 달라지는 포인트", "매출에 도움 되는 요약"],
        },
        cta_by_audience={
            **deepcopy(_CTA_SOFT),
            "동네 주민": {
                "title": "이웃에게도 전해 주세요",
                "subtitle": "예약·방문 전에 다시 볼 수 있게, 저장해 두세요",
                "body": "맛있었다면 좋아요, 추천 메뉴는 댓글로 남겨 주세요. 팔로우하면 다음 신메뉴도 받아볼 수 있어요",
            },
            "직장인": {
                "title": "동료에게도 살짝 공유해요",
                "subtitle": "점심 고민할 때 꺼내보도록, 저장해 두세요",
                "body": "도움이 됐다면 좋아요, 취향은 댓글로 남겨 주세요. 팔로우하면 다음 카드도 이어져요",
            },
        },
        sample_source=(
            "1. 오늘 신메뉴 출시\n"
            "제철 재료로 만든 시그니처 요리를 선보입니다.\n\n"
            "2. 왜 이 메뉴인가\n"
            "점심·저녁 모두 부담 없이 즐길 수 있게 구성했습니다.\n\n"
            "3. 추천 대상\n"
            "직장인 점심, 동네 주민 가족 식사에 잘 맞아요.\n\n"
            "4. 주문 팁\n"
            "인기 메뉴는 조기 마감될 수 있어요. 예약 추천!\n\n"
            "5. 이벤트\n"
            "이번 주 방문 시 음료 서비스. 리뷰 작성 시 디저트 증정."
        ),
    ),
    "personal_brand": _pack(
        topic_chips=["꿀팁", "후기", "사용법", "전후", "공지", "이벤트", "혜택가이드"],
        audience_chips=["입문자", "직장인", "사장님", "학생", "직장맘", "자취생"],
        photo_pools={
            "꿀팁": ["workspace", "laptop", "notebook", "creator", "desk", "coffee", "planner", "pen"],
            "후기": ["portrait", "smile", "lifestyle", "creator", "happy", "brand", "studio", "joy"],
            "사용법": ["tutorial", "laptop", "howto", "creator", "desk", "tools", "guide", "hands"],
            "전후": ["branding", "design", "portfolio", "studio", "style", "beforeafter", "creative", "work"],
            "공지": ["calendar", "desk", "laptop", "planner", "office", "notes", "schedule", "workspace"],
            "이벤트": ["live", "microphone", "stage", "creator", "audience", "lights", "event", "camera"],
            "혜택가이드": ["checklist", "planner", "notes", "laptop", "documents", "folder", "pen", "calendar"],
        },
        default_photo_pool=["creator", "workspace", "laptop", "portrait", "brand", "studio", "desk", "lifestyle"],
        cover_hooks_pair={
            ("꿀팁", "입문자"): "퍼스널브랜딩, 이것부터 시작하세요",
            ("꿀팁", "직장인"): "퇴근 후 3분, 프로필이 달라져요",
            ("후기", "사장님"): "브랜딩 후 문의가 달라진 이유",
            ("사용법", "학생"): "포트폴리오, 따라만 하면 돼요",
            ("전후", "입문자"): "프로필 전·후, 한눈에 비교",
        },
        cover_hooks_topic={
            "꿀팁": [
                "{audience}이 몰래 쓰는 브랜딩 팁",
                "알면 반응이 달라지는 {topic}",
                "오늘부터 바로 쓰는 팁",
            ],
            "후기": [
                "직접 해보니 달랐어요",
                "{audience} 반응이 좋은 이유",
                "성장이 느껴진 순간",
            ],
            "사용법": [
                "따라만 하면 되는 세팅법",
                "초보도 OK, 단계별 가이드",
                "프로필부터 콘텐츠까지",
            ],
            "전후": [
                "브랜딩 전·후 차이",
                "비주얼이 말해 주는 변화",
                "{audience}이 놀란 결과",
            ],
            "공지": [
                "놓치면 아쉬운 업데이트",
                "{audience}이 꼭 확인하세요",
                "짧게, 핵심만 정리",
            ],
            "이벤트": [
                "지금 참여하면 좋은 기회",
                "{audience} 위한 라이브·특강",
                "저장해 두고 신청하세요",
            ],
            "혜택가이드": [
                "협업·혜택만 쏙쏙",
                "{audience} 맞춤 가이드",
                "알아두면 이득인 안내",
            ],
        },
        cover_hooks_audience={
            "입문자": ["처음이어도 어렵지 않아요", "입문자가 가장 먼저 볼 내용"],
            "직장인": ["퇴근 후 3분이면 충분해요", "직장인이 저장하는 브랜딩"],
            "사장님": ["매출·신뢰로 이어지는 포인트", "사장님이 놓치지 않는 요약"],
            "학생": ["취업·포트폴리오에 바로 쓰는 팁", "학생이 공감하는 포인트"],
            "직장맘": ["바쁜 하루, 이것만은 챙기세요", "짧은 시간으로 만드는 존재감"],
            "자취생": ["혼라이프에도 통하는 브랜딩", "작은 루틴부터 시작"],
        },
        cta_by_audience={
            **deepcopy(_CTA_SOFT),
            "입문자": {
                "title": "입문 친구에게도 알려 주세요",
                "subtitle": "프로필 손보기 전에, 저장해 두세요",
                "body": "이해가 됐다면 좋아요, 궁금한 점은 댓글로 남겨 주세요. 팔로우하면 다음 브랜딩 카드도 이어져요",
            },
            "사장님": {
                "title": "사장님 커뮤니티에 공유해 보세요",
                "subtitle": "콘텐츠 기획에 참고하도록, 저장해 두세요",
                "body": "도움이 됐다면 좋아요, 현장 후기는 댓글로 남겨 주세요. 팔로우하면 운영·브랜딩 팁도 받아볼 수 있어요",
            },
        },
        sample_source=(
            "1. 이번 주 브랜딩 포인트\n"
            "프로필 한 줄이 인상을 바꿉니다.\n\n"
            "2. 왜 중요한가\n"
            "첫인상에서 신뢰가 결정되는 경우가 많아요.\n\n"
            "3. 추천 대상\n"
            "입문자, 직장인 사이드프로젝트, 사장님 개인 채널.\n\n"
            "4. 실천 팁\n"
            "소개 문구·대표 이미지·고정 게시물을 먼저 점검하세요.\n\n"
            "5. 다음 액션\n"
            "저장해 두고, 오늘 프로필부터 수정해 보세요."
        ),
    ),
    "custom": _pack(
        topic_chips=list(TOPICS),
        audience_chips=list(AUDIENCES),
        photo_pools={t: list(v) for t, v in {
            "신메뉴": ["product", "lifestyle", "minimal", "aesthetic", "studio", "display", "brand", "detail"],
            "후기": ["happy", "smile", "lifestyle", "friends", "portrait", "customer", "joy", "review"],
            "이벤트": ["celebration", "party", "lights", "crowd", "festival", "stage", "balloon", "event"],
            "꿀팁": ["notebook", "desk", "planner", "checklist", "pen", "workspace", "laptop", "tips"],
            "공지": ["bulletin", "office", "workspace", "sign", "paper", "desk", "board", "meeting"],
            "전후": ["beforeafter", "progress", "mirror", "studio", "portrait", "style", "change", "result"],
            "사용법": ["howto", "tutorial", "hands", "demo", "tools", "guide", "product", "steps"],
            "할인/프로모": ["sale", "gift", "coupon", "shopping", "bag", "retail", "offer", "promo"],
            "혜택가이드": ["checklist", "planner", "notes", "calendar", "documents", "folder", "pen", "guide"],
        }.items()},
        default_photo_pool=["lifestyle", "minimal", "aesthetic", "workspace", "brand", "studio", "creative", "modern"],
        cover_hooks_pair={},
        cover_hooks_topic={
            "신메뉴": ["새로 선보이는 {topic}", "{audience}이 궁금해할 소식", "첫인상부터 다르게"],
            "꿀팁": ["{audience}이 몰래 쓰는 {topic}", "알면 이득, 모르면 손해", "오늘부터 바로 쓰는 팁"],
            "후기": ["직접 경험한 솔직 후기", "{audience} 반응이 좋은 이유", "별점보다 생생한 이야기"],
            "이벤트": ["지금만 가능한 기회", "{audience} 위한 혜택", "저장해 두고 참여하세요"],
            "공지": ["놓치면 아쉬운 소식", "{audience}이 꼭 확인하세요", "짧게, 핵심만 정리"],
            "전후": ["변화, 눈으로 확인하세요", "전·후가 말해 주는 차이", "{audience}이 놀란 결과"],
            "사용법": ["따라만 하면 되는 가이드", "초보도 OK, 단계별 안내", "오늘 바로 적용해 보세요"],
            "할인/프로모": ["혜택, 지금이 타이밍", "{audience} 지갑 사수 팁", "할인 포인트만 모아봤어요"],
            "혜택가이드": ["혜택만 쏙쏙, 한 장 요약", "{audience} 맞춤 가이드", "알아두면 이득인 안내"],
        },
        cover_hooks_audience={
            "직장맘": ["바쁜 하루, 이것만은 챙기세요"],
            "자취생": ["자취생 필수, 이것부터"],
            "사장님": ["손님·고객 반응이 달라지는 포인트"],
            "입문자": ["처음이어도 어렵지 않아요"],
            "학부모": ["아이 위해 알아두면 좋은 정보"],
            "직장인": ["퇴근 전 3분이면 충분해요"],
            "동네 주민": ["우리 동네 소식, 핵심만"],
            "학생": ["학생이 공감하는 포인트"],
        },
        cta_by_audience=deepcopy(_CTA_SOFT),
        sample_source=(
            "1. 핵심 메시지\n"
            "전달하고 싶은 한 줄부터 적어 보세요.\n\n"
            "2. 왜 지금인가\n"
            "독자가 바로 공감할 이유를 짧게 적습니다.\n\n"
            "3. 추천 대상\n"
            "타겟이 얻는 이점을 구체적으로 적어요.\n\n"
            "4. 실천 팁\n"
            "바로 해볼 수 있는 행동을 1~2개 적습니다.\n\n"
            "5. 다음 액션\n"
            "저장·공유·문의 등 원하는 CTA를 안내하세요."
        ),
    ),
}


def normalize_concept_id(concept_id: str | None) -> str:
    cid = (concept_id or "").strip().lower()
    if cid in CONCEPT_PACKS:
        return cid
    return DEFAULT_CONCEPT_ID


def concept_label(concept_id: str | None) -> str:
    cid = normalize_concept_id(concept_id)
    return CONCEPT_LABELS.get(cid, cid)


def list_concepts() -> list[tuple[str, str]]:
    """[(id, korean_label), ...] in UI order."""
    return [(cid, CONCEPT_LABELS[cid]) for cid in CONCEPT_IDS]


def get_pack(concept_id: str | None) -> dict[str, Any]:
    return CONCEPT_PACKS[normalize_concept_id(concept_id)]


def topic_chips(concept_id: str | None) -> list[str]:
    chips = get_pack(concept_id)["topic_chips"]
    # Keep only known topics; fall back to full list if empty.
    filtered = [t for t in chips if t in TOPICS]
    return filtered or list(TOPICS)


def audience_chips(concept_id: str | None) -> list[str]:
    chips = get_pack(concept_id)["audience_chips"]
    filtered = [a for a in chips if a in AUDIENCES]
    return filtered or list(AUDIENCES)


def photo_pool_for(concept_id: str | None, topic: str) -> list[str]:
    pack = get_pack(concept_id)
    pools: dict[str, list[str]] = pack["photo_pools"]
    if topic in pools and pools[topic]:
        return list(pools[topic])
    return list(pack["default_photo_pool"])


def sample_source(concept_id: str | None) -> str:
    return str(get_pack(concept_id).get("sample_source") or "")


def cover_hook_from_pack(concept_id: str | None, topic: str, audience: str, pick_template) -> str:
    """Resolve cover hook using concept pack tables; pick_template(list, seed)->str."""
    pack = get_pack(concept_id)
    pair = pack["cover_hooks_pair"].get((topic, audience))
    if pair:
        return pair
    topic_list = pack["cover_hooks_topic"].get(topic)
    if topic_list:
        tmpl = pick_template(topic_list, f"{normalize_concept_id(concept_id)}|{topic}|{audience}|cover")
        return tmpl.format(topic=topic, audience=audience)
    aud_list = pack["cover_hooks_audience"].get(audience)
    if aud_list:
        tmpl = pick_template(aud_list, f"{normalize_concept_id(concept_id)}|{audience}|{topic}|cover")
        return tmpl.format(topic=topic, audience=audience)
    tmpl = pick_template(pack["generic_hooks"], f"{normalize_concept_id(concept_id)}|{topic}|{audience}")
    return tmpl.format(topic=topic, audience=audience)


def cta_from_pack(concept_id: str | None, audience: str) -> dict[str, str]:
    pack = get_pack(concept_id)
    base = pack["cta_by_audience"].get(audience) or pack["cta_default"]
    return dict(base)

"""인스타그램 카드뉴스 — 웹 간단 UI (구매자 UX 리빌드)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.admin_console import query_gate, render_admin_console, show_not_found
from src.auth import (
    admin_account_configured,
    admin_gate_configured,
    authenticate_admin,
    authenticate_buyer,
    merged_buyers,
    verify_admin_gate,
)
from src.auto_copy import auto_build_card_inputs
from src.buyer_settings import (
    MAX_CAPTION_TEMPLATES,
    MAX_TOPICS,
    add_schedule_job,
    due_pending_jobs,
    enabled_topics,
    get_buyer_settings,
    list_buyer_jobs,
    resolve_caption,
    save_buyer_settings,
    update_job_status,
)
from src.profiles import ensure_demo_profile, outputs_dir
from src.publisher import has_ig_credentials, publish_carousel, resolve_ig_credentials
from src.quota import (
    OVER_LIMIT_MSG,
    can_publish,
    record_publish,
    remaining_today,
    usage_summary_for_admin,
)
from src.renderer import generate_cardnews

load_dotenv()
ensure_demo_profile()

# Optional Streamlit Cloud secrets → env (Settings UI paste still overrides)
try:
    if "IG_ACCESS_TOKEN" in st.secrets and st.secrets["IG_ACCESS_TOKEN"]:
        import os

        os.environ.setdefault("IG_ACCESS_TOKEN", str(st.secrets["IG_ACCESS_TOKEN"]))
    if "IG_USER_ID" in st.secrets and st.secrets["IG_USER_ID"]:
        import os

        os.environ.setdefault("IG_USER_ID", str(st.secrets["IG_USER_ID"]))
except Exception:
    pass

st.set_page_config(
    page_title="인스타 카드뉴스",
    page_icon="📰",
    layout="centered",
)

# Default concept for renderer/RSS internals only (no buyer picker)
_DEFAULT_CONCEPT = "custom"
_DEFAULT_AUDIENCE = "구독자"
_DEFAULT_STYLE = "style.clean"

# ── Optional admin gate shortcut (?gate=). Primary admin: login tabs + pages/admin.py. ──
_gate_param = query_gate()
if _gate_param:
    if admin_gate_configured() and verify_admin_gate(_gate_param):
        render_admin_console()
        st.stop()
    if admin_gate_configured():
        show_not_found()

# ── session defaults ─────────────────────────────────────
ss = st.session_state
ss.setdefault("last_paths", [])
ss.setdefault("last_meta", {})
ss.setdefault("ig_token", "")
ss.setdefault("ig_user_id", "")
ss.setdefault("open_settings", False)
ss.setdefault("open_help", False)
ss.setdefault("last_news_titles", [])
ss.setdefault("last_source", "")
ss.setdefault("buyer_user", "")
ss.setdefault("buyer_authenticated", False)
ss.setdefault("admin_ok", False)
ss.setdefault("_schedules_processed", False)


def _mask_secret(value: str, keep: int = 4) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    prefix = v[:keep] if len(v) >= keep else v[: max(1, len(v) // 2)]
    return f"{prefix}…****"


def _clear_ig_from_url() -> None:
    try:
        for key in ("ig_uid", "ig_token", "token", "access_token"):
            if key in st.query_params:
                del st.query_params[key]
    except Exception:
        pass


def _ig_connected() -> bool:
    return has_ig_credentials(
        (ss.ig_token or "").strip(),
        (ss.ig_user_id or "").strip(),
    )


def _ig_status_label() -> str:
    if _ig_connected():
        tok, uid = resolve_ig_credentials(ss.ig_token, ss.ig_user_id)
        return f"연결됨 ✅ · {_mask_secret(tok)} / {_mask_secret(uid)}"
    return "⚪ 아직 연결 안 됨"


def _clear_ig_session() -> None:
    ss.ig_token = ""
    ss.ig_user_id = ""
    for k in ("settings_ig_token", "settings_ig_user_id"):
        if k in ss:
            del ss[k]
    _clear_ig_from_url()


def _buyer() -> str:
    return (ss.buyer_user or "").strip()


def _process_due_schedules() -> None:
    """Best-effort: when app loads, post due scheduled jobs (Streamlit Cloud)."""
    if ss.get("_schedules_processed"):
        return
    ss._schedules_processed = True
    jobs = due_pending_jobs()
    if not jobs:
        return
    for job in jobs:
        job_id = str(job.get("id") or "")
        username = str(job.get("username") or "")
        paths = [Path(p) for p in (job.get("image_paths") or [])]
        caption = str(job.get("caption") or "")
        missing = [p for p in paths if not p.exists()]
        if missing:
            update_job_status(
                job_id,
                status="failed",
                result_message=f"이미지 없음: {missing[0].name}",
            )
            continue
        ok_q, msg_q = can_publish(username)
        if not ok_q:
            update_job_status(job_id, status="failed", result_message=msg_q)
            continue
        # Use current session IG only if same buyer; else fail clearly
        if username != _buyer() or not _ig_connected():
            update_job_status(
                job_id,
                status="failed",
                result_message="예약 실행 시 해당 구매자로 로그인·인스타 연결이 필요해요.",
            )
            continue
        token_now = (ss.ig_token or "").strip()
        uid_now = (ss.ig_user_id or "").strip()
        result = publish_carousel(
            paths,
            caption,
            dry_run=False,
            access_token=token_now or None,
            ig_user_id=uid_now or None,
        )
        if result.ok and not result.dry_run:
            record_publish(username)
            update_job_status(job_id, status="done", result_message=result.message)
        elif result.ok and result.dry_run:
            update_job_status(
                job_id,
                status="failed",
                result_message="인스타 연결이 없어 실제 발행되지 않았어요.",
            )
        else:
            update_job_status(
                job_id, status="failed", result_message=result.message or "발행 실패"
            )


def _render_how_to_get_keys() -> None:
    st.markdown(
        """
**가장 쉬운 방법:** 판매자(안내해 준 분)에게 **연결 키 1·2**를 받아 위에 붙여 넣으세요.

판매자가 키를 만들 때 누르는 순서(참고):

1. 컴퓨터에서 **Meta 개발자 사이트**에 로그인합니다.
2. **앱 만들기**를 누릅니다. (처음이면 안내에 따라 앱 이름만 넣으면 됩니다)
3. 인스타그램 관련 **사용 항목**을 추가합니다.
4. 내 인스타 계정을 **테스터**로 넣고, 인스타 앱/알림에서 **수락**합니다.
5. **로그인·토큰 발급** 화면에서 긴 글(연결 키 1)을 복사합니다.
6. **계정 번호**(연결 키 2, 숫자)를 확인·복사합니다.
7. 이 앱 **설정**에 붙여 넣고 **저장**합니다. 먼저 **테스트발행**으로 확인해 보세요.

> 키는 비밀번호처럼 다루세요. **저장 후에는 화면에 숨겨집니다.**  
> 카톡·공개 채팅·깃허브·압축 파일에 키를 붙여 넣지 마세요.
"""
    )


def _render_settings_panel() -> None:
    """사이드바: 인스타 · 주제 · 캡션 템플릿 · 마무리 인사."""
    st.markdown("### ⚙️ 설정")
    if ss.buyer_user:
        st.caption(f"로그인: **{ss.buyer_user}**")
        if st.button("로그아웃", use_container_width=True, key="btn_buyer_logout"):
            ss.buyer_authenticated = False
            ss.buyer_user = ""
            ss.last_paths = []
            ss.last_meta = {}
            ss._schedules_processed = False
            _clear_ig_session()
            st.rerun()
    st.caption(_ig_status_label())

    usage = usage_summary_for_admin(_buyer()) if _buyer() else None
    if usage:
        st.info(
            f"오늘 발행 가능 **{usage['remaining']}**회 "
            f"(사용 {usage['used']}/{usage['limit']} · 서울 {usage['date']})"
        )

    st.markdown("#### 1. 인스타그램 연결")
    st.markdown(
        "인스타에 **직접 올리려면** 아래 두 칸만 채우면 됩니다. "
        "설치·설정 파일(`.env`)은 **필요 없어요.** "
        "**저장 후에는 키가 숨겨지고** 연결됨 ✅ / 마스킹만 보여요."
    )

    connected = _ig_connected()
    token_ph = (
        "저장됨(숨김) · 바꾸려면 새 키 입력"
        if connected
        else "판매자에게 받은 긴 글 붙여 넣기"
    )
    uid_ph = (
        "저장됨(숨김) · 바꾸려면 새 번호 입력"
        if connected
        else "판매자에게 받은 숫자"
    )
    token_in = st.text_input(
        "연결 키1 (토큰)",
        value="",
        type="password",
        placeholder=token_ph,
        help="비밀번호처럼 긴 연결 글입니다. 저장 후 전체 값은 다시 보이지 않습니다.",
        key="settings_ig_token",
    )
    uid_in = st.text_input(
        "연결 키2 (계정번호)",
        value="",
        type="password",
        placeholder=uid_ph,
        help="숫자로 된 계정 번호입니다. 저장 후 전체 값은 다시 보이지 않습니다.",
        key="settings_ig_user_id",
    )

    with st.expander("어떻게 받나요?", expanded=False):
        _render_how_to_get_keys()

    c_save, c_clear = st.columns(2)
    with c_save:
        if st.button("저장·연결", type="primary", use_container_width=True, key="btn_ig_save"):
            new_tok = (token_in or "").strip()
            new_uid = (uid_in or "").strip()
            if new_tok:
                ss.ig_token = new_tok
            if new_uid:
                ss.ig_user_id = new_uid
            _clear_ig_from_url()
            for k in ("settings_ig_token", "settings_ig_user_id"):
                if k in ss:
                    del ss[k]
            if _ig_connected():
                st.success(_ig_status_label())
                st.caption("전체 키는 숨겼어요. 공개 채팅에 붙여 넣지 마세요.")
            else:
                st.warning("연결 키1·키2를 모두 넣어 주세요.")
            st.rerun()
    with c_clear:
        if st.button("연결 끊기", use_container_width=True, key="btn_ig_clear"):
            _clear_ig_session()
            st.info("연결을 해제했어요. 세션의 키도 지웠어요.")
            st.rerun()

    if _ig_connected():
        st.success(_ig_status_label())
    else:
        st.info("연결 전에도 **카드 만들기·미리보기**는 가능해요.")

    st.divider()
    st.markdown("#### 2. 주제 (최대 5개)")
    st.caption("켜 둔 주제만 카드 만들기에 쓸 수 있어요. 자유롭게 적어 주세요.")

    settings = get_buyer_settings(_buyer())
    topics_ui = []
    for i in range(MAX_TOPICS):
        row = settings["topics"][i] if i < len(settings["topics"]) else {"text": "", "enabled": False}
        c1, c2 = st.columns([4, 1])
        with c1:
            t_text = st.text_input(
                f"주제 {i + 1}",
                value=row.get("text") or "",
                key=f"set_topic_text_{i}",
                placeholder="예: 카페 신메뉴, 봄 할인, AI 뉴스…",
            )
        with c2:
            st.write("")  # align with text input
            t_on = st.toggle(
                "켜기",
                value=bool(row.get("enabled")),
                key=f"set_topic_on_{i}",
            )
        topics_ui.append({"text": (t_text or "").strip(), "enabled": bool(t_on)})

    st.divider()
    st.markdown("#### 3. 인스타 본문 템플릿 (최대 5개)")
    st.caption(
        "슬라이드 글이 아니라 **인스타 업로드 본문**이에요. "
        "「직접 설정」이면 아래 글을 쓰고, 「AI에게 맡기기」면 주제·뉴스 제목으로 초안을 만듭니다. "
        "`{topic}` / `{주제}` 자리표시자 가능."
    )
    caps_ui = []
    for i in range(MAX_CAPTION_TEMPLATES):
        row = (
            settings["caption_templates"][i]
            if i < len(settings["caption_templates"])
            else {"text": "", "mode": "ai", "enabled": False}
        )
        with st.expander(f"본문 템플릿 {i + 1}", expanded=(i == 0)):
            c_on = st.toggle(
                "사용",
                value=bool(row.get("enabled")),
                key=f"set_cap_on_{i}",
            )
            mode_manual = st.toggle(
                "직접 설정 (끄면 AI에게 맡기기)",
                value=(str(row.get("mode") or "manual") == "manual"),
                key=f"set_cap_manual_{i}",
            )
            c_text = st.text_area(
                "본문 내용",
                value=row.get("text") or "",
                height=100,
                key=f"set_cap_text_{i}",
                placeholder="예: [{topic}] 오늘의 한 줄\n\n#카드뉴스 #{topic}",
                disabled=not mode_manual,
            )
            caps_ui.append(
                {
                    "text": c_text or "",
                    "mode": "manual" if mode_manual else "ai",
                    "enabled": bool(c_on),
                }
            )

    st.divider()
    st.markdown("#### 4. 마무리·고정 문구")
    greet_in = st.text_area(
        "마무리 인사 (마지막 참여유도 슬라이드)",
        value=settings.get("closing_greeting") or "",
        height=68,
        key="settings_closing_greeting",
        placeholder="예: 오늘도 응원해요 💛",
    )
    always_in = st.text_area(
        "항상 넣을 내용 (카드 본문)",
        value=settings.get("always_include") or "",
        height=80,
        key="settings_always_include",
        placeholder="예: 매일 10–22시 · 주차 2시간 무료",
    )

    if st.button("설정 저장", type="primary", use_container_width=True, key="btn_settings_save"):
        payload = {
            "topics": topics_ui,
            "caption_templates": caps_ui,
            "closing_greeting": (greet_in or "").strip(),
            "always_include": (always_in or "").strip(),
        }
        ok, msg = save_buyer_settings(_buyer(), payload)
        if ok:
            st.success("설정을 저장했어요.")
            st.rerun()
        else:
            st.error(f"저장 실패: {msg}")

    st.divider()
    st.caption("주제·본문 템플릿은 계정별로 저장돼요. 인스타 키는 이 창 세션에만 두고 저장 후 숨겨요.")


def _render_help_panel() -> None:
    st.markdown("### ❓ 도움말")
    tab_use, tab_ig, tab_faq = st.tabs(["사용법", "인스타 연결", "자주 묻는 질문"])

    with tab_use:
        st.markdown(
            """
**한 줄 흐름:** 로그인 → 설정(주제·본문·인스타) → **주제 골라 카드 만들기** → 미리보기 → **테스트 / 즉시 / 예약** 발행

1. 판매자에게 받은 **아이디·비밀번호**로 로그인합니다.
2. 왼쪽 **설정**에서 주제(최대 5)·본문 템플릿·인스타 연결을 저장합니다.
3. 본문에서 **켜 둔 주제**를 고르고 **카드 만들기**를 누릅니다.
   - 무료 **구글 뉴스 RSS**에서 관련 소식을 가져옵니다. (API 키 없음)
   - 마지막 장은 항상 **참여유도(CTA)** 입니다.
4. 미리보기 후 올리기 방식을 고릅니다.
   - **테스트발행** = 실제로 안 올림 · **하루 한도 차감 없음**
   - **즉시발행** = 연결 키로 바로 게시 · 성공 시 한도 차감
   - **예약발행** = 날짜·시간 저장 · 앱을 열 때 기한이 된 예약을 처리

**팁**
- 주제는 짧게 (예: `신메뉴`, `봄 할인`, `수강 모집`).
- 본문 템플릿의 `{topic}` / `{주제}`는 선택한 주제로 바뀝니다.
"""
        )

    with tab_ig:
        st.markdown(
            """
**구매자:** 판매자에게 **연결 키1(토큰)** / **연결 키2(계정번호)** 를 받아  
왼쪽 **설정**에 붙여 넣고 **저장·연결**만 하면 됩니다.

저장 후에는 전체 키가 **숨겨지고**, **연결됨 ✅** 와 마스킹만 보여요.  
키를 **공개 채팅·카톡·깃허브**에 붙여 넣지 마세요.
"""
        )
        _render_how_to_get_keys()

    with tab_faq:
        st.markdown(
            """
**Q. 하루 몇 번 올릴 수 있나요?**  
A. 기본 **하루 3회**(서울 날짜 기준)입니다. 한도를 넘으면 「추가 발행은 관리자에게 문의하세요」가 나와요. 테스트발행은 한도를 쓰지 않아요.

**Q. 뉴스는 어디서 가져오나요?**  
A. 무료 **Google News RSS**입니다. API 키·결제가 없습니다.

**Q. AI(유료)를 쓰나요?**  
A. 아니요. 뉴스 제목·요약을 템플릿으로 정리하고, 본문 「AI에게 맡기기」도 휴리스틱 초안입니다.

**Q. 예약은 언제 올라가요?**  
A. Streamlit은 항상 켜져 있지 않아서, **앱을 열 때** 기한이 된 예약을 처리합니다. (열린 동안 같은 구매자·인스타 연결 필요)

**Q. 연결 안 했는데 카드를 만들 수 있나요?**  
A. 네. 미리보기·테스트까지는 연결 없이 됩니다. 즉시/예약 실제 발행만 연결이 필요합니다.

**Q. 콘셉트·업종 칩이 없어요?**  
A. 맞아요. 주제만 직접 적어 쓰면 됩니다.
"""
        )


_clear_ig_from_url()


def _render_login_screen() -> None:
    """구매자 / 관리자 로그인 탭 — 통과 전에는 카드 기능 비표시."""
    st.title("📰 인스타 카드뉴스")
    tab_buyer, tab_admin = st.tabs(["구매자 로그인", "관리자 로그인"])

    with tab_buyer:
        st.caption("판매자에게 받은 아이디·비밀번호로 로그인해 주세요.")
        st.caption("관리자면 위쪽 관리자 로그인 탭을 누르세요.")
        with st.form("buyer_login_form"):
            uid = st.text_input("아이디", placeholder="판매자에게 받은 아이디")
            pw = st.text_input("비밀번호", type="password", placeholder="비밀번호")
            ok = st.form_submit_button("로그인", type="primary", use_container_width=True)
        if ok:
            good, msg = authenticate_buyer(uid or "", pw or "")
            if good:
                ss.buyer_authenticated = True
                ss.buyer_user = (uid or "").strip()
                ss._schedules_processed = False
                st.success("로그인됐어요.")
                st.rerun()
            else:
                st.error(msg)
        st.divider()
        st.caption("계정이 없으면 판매자에게 문의해 주세요.")
        if not merged_buyers():
            st.info("아직 등록된 구매자 계정이 없어요. 판매자에게 계정 발급을 요청해 주세요.")

    with tab_admin:
        st.caption("판매자 전용 · Secrets의 관리자 아이디/비밀번호로 로그인합니다.")
        if not admin_account_configured():
            st.error(
                "관리자 계정이 없어요. Streamlit Secrets에 "
                "`ADMIN_USERNAME` 과 `ADMIN_PASSWORD`(또는 `ADMIN_PASSWORD_HASH`) 를 넣어 주세요."
            )
        else:
            with st.form("admin_login_main_form"):
                admin_id = st.text_input(
                    "아이디", key="admin_main_id", autocomplete="username"
                )
                admin_pw = st.text_input(
                    "비밀번호",
                    type="password",
                    key="admin_main_pw",
                    autocomplete="current-password",
                )
                admin_ok_btn = st.form_submit_button(
                    "관리자 로그인", type="primary", use_container_width=True
                )
            if admin_ok_btn:
                if authenticate_admin(admin_id or "", admin_pw or ""):
                    ss.admin_ok = True
                    ss.admin_flash = "로그인 완료."
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 올바르지 않아요.")
        st.caption("사이드바 **admin**(관리자) 페이지로도 들어갈 수 있어요.")


# Admin session: show console on main URL (also available via pages/admin.py)
if ss.get("admin_ok"):
    render_admin_console()
    st.stop()

if not (ss.buyer_authenticated and ss.buyer_user):
    _render_login_screen()
    st.stop()

# Best-effort process due schedules once per session load
_process_due_schedules()

# ── 사이드바: 설정 + 도움말 ───────────────────────────────
with st.sidebar:
    _render_settings_panel()
    st.divider()
    _render_help_panel()

# ── 본문 ─────────────────────────────────────────────────
st.title("📰 인스타 카드뉴스")
st.caption("주제 고르기 → 카드 만들기(최신 뉴스) → 미리보기 → 테스트 / 즉시 / 예약 발행")

status_cols = st.columns([3, 1])
with status_cols[0]:
    if _ig_connected():
        st.success(f"인스타 {_ig_status_label()}")
    else:
        st.info("인스타 연결은 **선택**이에요. 왼쪽 설정에서 언제든 연결할 수 있어요.")
with status_cols[1]:
    rem = remaining_today(_buyer())
    st.metric("오늘 남은 발행", rem)

topics = enabled_topics(_buyer())
settings = get_buyer_settings(_buyer())

# ── 1. 주제 선택 ─────────────────────────────────────────
st.subheader("1. 주제 고르기")
if not topics:
    st.warning(
        "켜 둔 주제가 없어요. 왼쪽 **설정 → 주제**에서 주제를 적고 토글을 켠 뒤 **설정 저장**해 주세요."
    )
    topic_now = ""
else:
    topic_now = st.radio(
        "오늘 만들 주제",
        topics,
        horizontal=True if len(topics) <= 3 else False,
        key="pick_enabled_topic",
    )
    st.caption("한 번에 한 주제씩 카드를 만들어요.")

# ── 2. 카드 만들기 ───────────────────────────────────────
st.subheader("2. 카드 만들기")
can_gen = bool(topic_now and str(topic_now).strip())
if st.button(
    "카드 만들기",
    type="primary",
    disabled=not can_gen,
    use_container_width=True,
    key="btn_auto_gen",
):
    out = outputs_dir("web")
    closing = settings.get("closing_greeting") or ""
    always = settings.get("always_include") or ""
    with st.spinner("관련 뉴스 찾는 중… 카드 만드는 중…"):
        result = auto_build_card_inputs(
            topic=str(topic_now).strip(),
            audience=_DEFAULT_AUDIENCE,
            concept_id=_DEFAULT_CONCEPT,
            concept_label="",
            caption_template="",  # caption resolved separately via templates
            always_include=always,
            closing_greeting=closing,
        )
        for w in result.warnings:
            st.warning(w)
        if result.news_items:
            st.caption(
                "가져온 소식: "
                + " · ".join(n.title[:40] for n in result.news_items[:4])
            )
        paths = generate_cardnews(
            topic=result.topic,
            audience=result.audience,
            source=result.source,
            style_id=_DEFAULT_STYLE,
            out_dir=out,
            profile_name="웹",
            concept_id=_DEFAULT_CONCEPT,
            closing_greeting=closing,
        )
    headlines = [n.title for n in result.news_items]
    caption = resolve_caption(
        username=_buyer(),
        topic=result.topic,
        headlines=headlines,
    )
    ss.last_paths = [str(p) for p in paths]
    ss.last_source = result.source
    ss.last_news_titles = headlines
    ss.last_meta = {
        "topic": result.topic,
        "audience": result.audience,
        "style_id": _DEFAULT_STYLE,
        "concept_id": _DEFAULT_CONCEPT,
        "caption": caption,
        "mode": "auto_news",
        "query": result.query,
    }
    ss._caption_seed = caption
    ss.preview_caption = caption
    st.success(f"{len(paths)}장 준비됐어요 (마지막 장 = 참여유도) ↓")

paths = ss.last_paths
meta = ss.last_meta

if paths:
    st.markdown(f"**미리보기** · {meta.get('topic', '')} · 자동(뉴스)")
    if meta.get("query"):
        st.caption(f"검색어: {meta.get('query')}")
    if ss.last_news_titles:
        with st.expander("참고한 뉴스 제목", expanded=False):
            for t in ss.last_news_titles:
                st.markdown(f"- {t}")

    n = len(paths)
    cols = st.columns(min(n, 4))
    for i, p in enumerate(paths):
        with cols[i % len(cols)]:
            if Path(p).exists():
                label = f"{i+1}/{n}" + (" · 참여유도" if i == n - 1 else "")
                st.image(p, caption=label, use_container_width=True)
            else:
                st.error(f"없음: {p}")

    default_caption = meta.get("caption") or resolve_caption(
        username=_buyer(),
        topic=meta.get("topic", topic_now or ""),
        headlines=ss.last_news_titles or [],
    )
    if ss.get("_caption_seed") != default_caption and "preview_caption" not in ss:
        ss._caption_seed = default_caption
        ss.preview_caption = default_caption
    caption = st.text_area(
        "인스타 본문 (올리기 전 수정 가능)",
        height=120,
        key="preview_caption",
    )

    # ── 3. 발행 ───────────────────────────────────────────
    st.subheader("3. 인스타에 올리기")
    usage = usage_summary_for_admin(_buyer())
    st.caption(
        f"오늘 남은 발행 **{usage['remaining']}**회 "
        f"(사용 {usage['used']}/{usage['limit']} · 서울 기준). "
        "테스트발행은 한도를 쓰지 않아요."
    )

    if _ig_connected():
        st.success(f"설정 연결 사용 중 · {_ig_status_label()}")
    else:
        st.warning(
            "아직 인스타가 연결되지 않았어요. "
            "**즉시발행·예약발행**을 쓰려면 왼쪽 **설정**에서 연결 키1·키2를 저장해 주세요. "
            "테스트발행은 연결 없이 가능합니다."
        )

    mode = st.radio(
        "발행 방식",
        ["테스트발행", "즉시발행", "예약발행"],
        index=0,
        horizontal=True,
        key="publish_mode_radio",
    )

    sched_dt = None
    if mode == "예약발행":
        from zoneinfo import ZoneInfo

        seoul = ZoneInfo("Asia/Seoul")
        now_s = datetime.now(seoul)
        d = st.date_input("예약 날짜 (서울)", value=now_s.date(), key="sched_date")
        t = st.time_input(
            "예약 시간 (서울)",
            value=(now_s + timedelta(hours=1)).replace(second=0, microsecond=0).time(),
            key="sched_time",
        )
        sched_dt = datetime.combine(d, t).replace(tzinfo=seoul)

    token_now = (ss.ig_token or "").strip()
    uid_now = (ss.ig_user_id or "").strip()

    if st.button("실행", type="primary", use_container_width=True, key="btn_publish"):
        if mode == "테스트발행":
            with st.spinner("테스트(연습) 중…"):
                result = publish_carousel(
                    [Path(p) for p in paths],
                    caption,
                    dry_run=True,
                    access_token=token_now or None,
                    ig_user_id=uid_now or None,
                )
            if result.ok:
                st.success(result.message + " · 하루 한도는 차감되지 않았어요.")
            else:
                st.error(result.message)
            if result.raw and not result.ok:
                with st.expander("문제 해결용 정보 (판매자 전달용)"):
                    st.json(result.raw)

        elif mode == "즉시발행":
            ok_q, msg_q = can_publish(_buyer())
            if not ok_q:
                st.error(msg_q)
            elif not has_ig_credentials(token_now, uid_now):
                st.error(
                    "즉시발행하려면 왼쪽 **설정**에서 인스타 연결(연결 키1·키2 저장)이 필요해요."
                )
            else:
                with st.spinner("발행 중…"):
                    result = publish_carousel(
                        [Path(p) for p in paths],
                        caption,
                        dry_run=False,
                        access_token=token_now or None,
                        ig_user_id=uid_now or None,
                    )
                if result.ok and not result.dry_run:
                    record_publish(_buyer())
                    st.success(result.message + f" · 남은 발행 {remaining_today(_buyer())}회")
                elif result.ok and result.dry_run:
                    st.error("인스타 연결을 확인할 수 없어 실제로 올라가지 않았어요. 한도는 차감하지 않았어요.")
                else:
                    st.error(result.message)
                if result.raw and not result.ok:
                    with st.expander("문제 해결용 정보 (판매자 전달용)"):
                        st.json(result.raw)

        elif mode == "예약발행":
            ok_q, msg_q = can_publish(_buyer())
            if not ok_q:
                st.error(msg_q + " (예약도 실제 발행 시 한도를 씁니다)")
            elif sched_dt is None:
                st.error("예약 시간을 확인해 주세요.")
            elif not has_ig_credentials(token_now, uid_now):
                st.error("예약발행도 인스타 연결이 필요해요. 설정에서 키를 저장해 주세요.")
            else:
                ok, msg, job = add_schedule_job(
                    username=_buyer(),
                    run_at_iso=sched_dt.isoformat(),
                    image_paths=list(paths),
                    caption=caption or "",
                    topic=str(meta.get("topic") or ""),
                )
                if ok:
                    st.success(
                        f"{msg} · {sched_dt.strftime('%Y-%m-%d %H:%M')} (서울) · "
                        "앱을 열 때 기한이 되면 발행을 시도해요. 한도는 **실제 발행 성공 시** 차감됩니다."
                    )
                else:
                    st.error(msg)

    pending = list_buyer_jobs(_buyer(), include_done=True)
    if pending:
        with st.expander("내 예약·발행 기록", expanded=False):
            for j in pending[-10:]:
                st.markdown(
                    f"- `{j.get('status')}` · {j.get('run_at')} · "
                    f"{(j.get('topic') or '')[:30]} · {j.get('result_message') or ''}"
                )
else:
    st.caption("주제를 고르고 **카드 만들기**를 누르면 여기에 미리보기가 나타나요.")

st.divider()
st.caption("카드 미리보기만 해도 돼요. 인스타 올리기는 선택 사항입니다.")
st.caption("📷 배경 사진은 무료 이미지 소스 사용 (비용 없음). 마지막 슬라이드 = 참여유도.")

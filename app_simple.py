"""인스타그램 카드뉴스 — 웹 간단 UI."""
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv
from src.admin_console import query_gate, render_admin_console, show_not_found
from src.auth import (
    admin_account_configured, admin_gate_configured, authenticate_admin,
    authenticate_buyer, clear_login_failures, login_rate_limited, merged_buyers,
    record_login_failure, verify_admin_gate,
)
from src.auto_copy import auto_build_card_inputs
from src.ai_providers import PROVIDERS, mask_api_key, provider_label
from src.buyer_settings import (
    MAX_CAPTION_TEMPLATES, MAX_TOPICS, add_schedule_job, due_pending_jobs,
    enabled_topics, get_buyer_settings, list_buyer_jobs, resolve_caption,
    save_buyer_settings, update_job_status,
)
from src.profiles import ensure_demo_profile, outputs_dir
from src.publisher import has_ig_credentials, publish_carousel, resolve_ig_credentials
from src.quota import can_publish, record_publish, remaining_today, usage_summary_for_admin
from src.renderer import generate_cardnews

load_dotenv(); ensure_demo_profile()
try:
    import os
    if "IG_ACCESS_TOKEN" in st.secrets and st.secrets["IG_ACCESS_TOKEN"]:
        os.environ.setdefault("IG_ACCESS_TOKEN", str(st.secrets["IG_ACCESS_TOKEN"]))
    if "IG_USER_ID" in st.secrets and st.secrets["IG_USER_ID"]:
        os.environ.setdefault("IG_USER_ID", str(st.secrets["IG_USER_ID"]))
except Exception:
    pass

st.set_page_config(page_title="인스타 카드뉴스", page_icon="📰", layout="centered")
_DEFAULT_CONCEPT, _DEFAULT_AUDIENCE, _DEFAULT_STYLE = "custom", "구독자", "style.clean"

_gate_param = query_gate()
if _gate_param:
    if admin_gate_configured() and verify_admin_gate(_gate_param):
        render_admin_console(); st.stop()
    if admin_gate_configured():
        show_not_found()

ss = st.session_state
for k, v in {
    "last_paths": [], "last_meta": {}, "ig_token": "", "ig_user_id": "",
    "last_news_titles": [], "last_source": "", "buyer_user": "",
    "buyer_authenticated": False, "admin_ok": False, "_schedules_processed": False,
}.items():
    ss.setdefault(k, v)

def _mask(v, keep=4):
    v = (v or "").strip()
    if not v: return ""
    return f"{v[:keep]}…****"

def _clear_ig_url():
    try:
        for key in ("ig_uid", "ig_token", "token", "access_token"):
            if key in st.query_params: del st.query_params[key]
    except Exception:
        pass

def _own_ig():
    return bool((ss.ig_token or "").strip() and (ss.ig_user_id or "").strip())

def _buyer():
    return (ss.buyer_user or "").strip()

def _ig_label():
    if not _own_ig():
        return "⚪ 아직 연결 안 됨"
    tok, uid = resolve_ig_credentials(ss.ig_token, ss.ig_user_id)
    return f"연결됨 ✅ · {_mask(tok)} / {_mask(uid)}"

def _load_secrets():
    u = _buyer()
    if not u or ss.get("_buyer_secrets_loaded_for") == u:
        return
    conf = get_buyer_settings(u)
    if not (ss.ig_token or "").strip() and conf.get("ig_access_token"):
        ss.ig_token = str(conf.get("ig_access_token") or "")
    if not (ss.ig_user_id or "").strip() and conf.get("ig_user_id"):
        ss.ig_user_id = str(conf.get("ig_user_id") or "")
    ss.setdefault("ai_provider", str(conf.get("ai_provider") or ""))
    ss.setdefault("ai_api_key", str(conf.get("ai_api_key") or ""))
    ss._buyer_secrets_loaded_for = u

def _usage(key, title, md):
    if hasattr(st, "dialog"):
        @st.dialog(title)
        def _dlg():
            st.markdown(md)
            st.caption("비용·키 보관은 본인 책임이에요.")
            if st.button("닫기", key=f"{key}_c", use_container_width=True):
                st.rerun()
        if st.button("사용법", key=f"u_{key}"):
            _dlg()
    else:
        with st.expander("사용법 보기"):
            st.markdown(md)

_IG1 = "1. 인스타를 비즈니스/크리에이터로 준비\n2. Meta 개발자에서 앱·긴 글(토큰) 발급\n3. 복사 → 연결 키1에 붙여 넣기 → 저장"
_IG2 = "1. 토큰과 같이 보이는 숫자 계정 번호 확인\n2. 연결 키2에 붙여 넣기 → 저장\n3. 키1·키2는 같은 계정이어야 해요"
_AI = {
    "gemini": "1. Google AI Studio 로그인\n2. API 키 만들기\n3. 복사해 붙여 넣기\n4. 요금은 구매자 부담",
    "openai": "1. OpenAI 로그인\n2. API keys → Create\n3. 복사해 붙여 넣기\n4. 요금은 구매자 부담",
    "anthropic": "1. Anthropic 콘솔 로그인\n2. API Keys 발급\n3. 복사해 붙여 넣기\n4. 요금은 구매자 부담",
    "xai": "1. xAI 콘솔 로그인\n2. API 키 발급\n3. 복사해 붙여 넣기\n4. 요금은 구매자 부담",
    "openrouter": "1. OpenRouter 가입\n2. Keys에서 키 발급\n3. 복사해 붙여 넣기\n4. 요금은 구매자 부담",
}

def _settings():
    st.markdown("### ⚙️ 설정")
    if ss.buyer_user:
        st.caption(f"로그인: **{ss.buyer_user}**")
        if st.button("로그아웃", use_container_width=True, key="lo"):
            ss.buyer_authenticated = False; ss.buyer_user = ""
            ss.last_paths = []; ss.last_meta = {}; ss._schedules_processed = False
            ss.ig_token = ""; ss.ig_user_id = ""; _clear_ig_url(); st.rerun()
    st.caption(_ig_label())
    usage = usage_summary_for_admin(_buyer()) if _buyer() else None
    if usage:
        st.info(f"오늘 발행 가능 **{usage['remaining']}**회 (사용 {usage['used']}/{usage['limit']})")

    st.markdown("#### 1. 인스타 연결 (내 계정)")
    st.caption("실제로 올리려면 내 인스타 키 두 칸을 채우세요. 저장 후 숨겨져요.")
    conn = _own_ig()
    t_in = st.text_input("연결 키1 (긴 글)", value="", type="password",
        placeholder="저장됨(숨김)" if conn else "본인 인스타 긴 글 붙여 넣기", key="s_ig_t")
    _usage("ig1", "연결 키1 사용법", _IG1)
    u_in = st.text_input("연결 키2 (계정 번호)", value="", type="password",
        placeholder="저장됨(숨김)" if conn else "본인 인스타 숫자 붙여 넣기", key="s_ig_u")
    _usage("ig2", "연결 키2 사용법", _IG2)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("저장·연결", type="primary", use_container_width=True, key="ig_save"):
            if (t_in or "").strip(): ss.ig_token = t_in.strip()
            if (u_in or "").strip(): ss.ig_user_id = u_in.strip()
            _clear_ig_url()
            if _buyer():
                cur = get_buyer_settings(_buyer())
                cur["ig_access_token"] = (ss.ig_token or "").strip()
                cur["ig_user_id"] = (ss.ig_user_id or "").strip()
                save_buyer_settings(_buyer(), cur)
            st.rerun()
    with c2:
        if st.button("연결 끊기", use_container_width=True, key="ig_clr"):
            ss.ig_token = ""; ss.ig_user_id = ""; _clear_ig_url()
            if _buyer():
                cur = get_buyer_settings(_buyer())
                cur["ig_access_token"] = ""; cur["ig_user_id"] = ""
                save_buyer_settings(_buyer(), cur)
            st.rerun()

    st.markdown("#### 2. 주제 (최대 5개)")
    settings = get_buyer_settings(_buyer())
    topics_ui = []
    for i in range(MAX_TOPICS):
        row = settings["topics"][i] if i < len(settings["topics"]) else {"text": "", "enabled": False}
        a, b = st.columns([4, 1])
        with a:
            t = st.text_input(f"주제 {i+1}", value=row.get("text") or "", key=f"tt{i}",
                placeholder="예: 신메뉴, 봄 할인…")
        with b:
            st.write(""); on = st.toggle("켜기", value=bool(row.get("enabled")), key=f"to{i}")
        topics_ui.append({"text": (t or "").strip(), "enabled": bool(on)})

    st.markdown("#### 3. 본문 템플릿")
    caps_ui = []
    for i in range(MAX_CAPTION_TEMPLATES):
        row = settings["caption_templates"][i] if i < len(settings["caption_templates"]) else {"text": "", "mode": "ai", "enabled": False}
        with st.expander(f"본문 템플릿 {i+1}", expanded=(i == 0)):
            on = st.toggle("사용", value=bool(row.get("enabled")), key=f"co{i}")
            man = st.toggle("직접 설정 (끄면 AI)", value=(str(row.get("mode") or "manual") == "manual"), key=f"cm{i}")
            tx = st.text_area("본문", value=row.get("text") or "", height=80, key=f"ct{i}", disabled=not man)
            caps_ui.append({"text": tx or "", "mode": "manual" if man else "ai", "enabled": bool(on)})

    st.markdown("#### 4. AI 본문 (본인 키)")
    st.caption("키가 없으면 「키 없이 간단 초안」만 씁니다. 요금은 구매자 부담.")
    prov_ids = [p["id"] for p in PROVIDERS]
    cur = (ss.get("ai_provider") or settings.get("ai_provider") or "").strip().lower()
    if cur not in prov_ids: cur = prov_ids[0]
    pick = st.selectbox("AI 제공자", options=prov_ids, index=prov_ids.index(cur),
        format_func=lambda x: provider_label(x), key="ai_prov")
    saved = (ss.get("ai_api_key") or settings.get("ai_api_key") or "").strip()
    ak = st.text_input(f"API 키 ({provider_label(pick)})", value="", type="password",
        placeholder=f"저장됨 {mask_api_key(saved)}" if saved else "본인 API 키", key="ai_key")
    _usage(f"ai_{pick}", f"{provider_label(pick)} 사용법", _AI.get(pick, "해당 사이트에서 키 발급 후 붙여 넣기"))
    if st.button("AI 설정 저장", use_container_width=True, key="ai_save"):
        ss.ai_provider = pick
        if (ak or "").strip(): ss.ai_api_key = ak.strip()
        elif saved: ss.ai_api_key = saved
        if _buyer():
            cur = get_buyer_settings(_buyer())
            cur["ai_provider"] = pick
            if (ak or "").strip(): cur["ai_api_key"] = ak.strip()
            elif saved: cur["ai_api_key"] = saved
            save_buyer_settings(_buyer(), cur)
            st.success("저장했어요"); st.rerun()

    st.markdown("#### 5. 마무리 문구")
    greet = st.text_area("마무리 인사", value=settings.get("closing_greeting") or "", height=60, key="gr")
    always = st.text_area("항상 넣을 내용", value=settings.get("always_include") or "", height=60, key="al")
    if st.button("설정 저장", type="primary", use_container_width=True, key="sv"):
        ok, msg = save_buyer_settings(_buyer(), {
            "topics": topics_ui, "caption_templates": caps_ui,
            "closing_greeting": (greet or "").strip(), "always_include": (always or "").strip(),
        })
        st.success("저장했어요") if ok else st.error(msg)
        if ok: st.rerun()

_clear_ig_url()

def _login():
    st.title("📰 인스타 카드뉴스")
    tb, ta = st.tabs(["구매자 로그인", "관리자 로그인"])
    with tb:
        st.caption("판매자에게 받은 아이디·비밀번호로 로그인해 주세요.")
        with st.form("bl"):
            uid = st.text_input("아이디"); pw = st.text_input("비밀번호", type="password")
            ok = st.form_submit_button("로그인", type="primary", use_container_width=True)
        if ok:
            blocked, bm = login_rate_limited(ss, "buyer")
            if blocked: st.error(bm)
            else:
                good, msg = authenticate_buyer(uid or "", pw or "")
                if good:
                    clear_login_failures(ss, "buyer")
                    ss.buyer_authenticated = True; ss.buyer_user = (uid or "").strip()
                    ss._schedules_processed = False; ss._buyer_secrets_loaded_for = ""
                    _load_secrets(); st.success("로그인됐어요."); st.rerun()
                else:
                    st.error(record_login_failure(ss, "buyer"))
        if not merged_buyers():
            st.info("등록된 구매자 계정이 없어요. 판매자에게 문의해 주세요.")
    with ta:
        if not admin_account_configured():
            st.error("Secrets에 ADMIN_USERNAME + ADMIN_PASSWORD_HASH(또는 ADMIN_PASSWORD)를 넣어 주세요.")
        else:
            with st.form("al"):
                aid = st.text_input("아이디", key="aid"); apw = st.text_input("비밀번호", type="password", key="apw")
                aok = st.form_submit_button("관리자 로그인", type="primary", use_container_width=True)
            if aok:
                blocked, bm = login_rate_limited(ss, "admin")
                if blocked: st.error(bm)
                elif authenticate_admin(aid or "", apw or ""):
                    clear_login_failures(ss, "admin"); ss.admin_ok = True; st.rerun()
                else:
                    st.error(record_login_failure(ss, "admin"))

if ss.get("admin_ok"):
    render_admin_console(); st.stop()
if not (ss.buyer_authenticated and ss.buyer_user):
    _login(); st.stop()

_load_secrets()
with st.sidebar:
    _settings()

st.title("📰 인스타 카드뉴스")
st.caption("① 주제 고르기 → ② 카드 만들기 → ③ 미리보기 → ④ 올리기")
topics = enabled_topics(_buyer())
settings = get_buyer_settings(_buyer())
prev = ss.get("last_paths") or []
if not topics:
    st.warning("다음: 왼쪽 **설정 → 주제**에서 주제를 적고 켠 뒤 **설정 저장**해 주세요.")
elif not prev:
    st.info("다음: 아래에서 주제를 고르고 **카드 만들기**를 눌러 주세요.")
elif not _own_ig():
    st.info("다음: 미리보기·**테스트**는 가능 · 실제 발행은 왼쪽 설정에서 **인스타 연결**이 필요해요.")
else:
    st.success(f"준비됨 · 인스타 {_ig_label()} · 아래에서 올리기 방식을 고르세요.")

cA, cB = st.columns([3, 1])
with cA: st.caption("설정·인스타·AI 키는 왼쪽 사이드바에 있어요.")
with cB: st.metric("오늘 남은 발행", remaining_today(_buyer()))

st.subheader("1. 주제 고르기")
topic_now = "" if not topics else st.selectbox("오늘 만들 주제", topics, key="pick_enabled_topic",
    help="설정에서 켠 주제만 보여요.")

st.subheader("2. 카드 만들기")
if st.button("카드 만들기", type="primary", disabled=not bool(topic_now), use_container_width=True, key="gen"):
    out = outputs_dir("web")
    closing = settings.get("closing_greeting") or ""
    always = settings.get("always_include") or ""
    with st.spinner("카드 만드는 중…"):
        result = auto_build_card_inputs(
            topic=str(topic_now).strip(), audience=_DEFAULT_AUDIENCE,
            concept_id=_DEFAULT_CONCEPT, concept_label="", caption_template="",
            always_include=always, closing_greeting=closing,
        )
        paths = generate_cardnews(
            topic=result.topic, audience=result.audience, source=result.source,
            style_id=_DEFAULT_STYLE, out_dir=out, profile_name="웹",
            concept_id=_DEFAULT_CONCEPT, closing_greeting=closing,
        )
    headlines = [n.title for n in result.news_items]
    caption = resolve_caption(username=_buyer(), topic=result.topic, headlines=headlines)
    ss.last_paths = [str(p) for p in paths]
    ss.last_news_titles = headlines
    ss.last_meta = {"topic": result.topic, "caption": caption, "query": result.query}
    ss.preview_caption = caption
    st.success(f"{len(paths)}장 준비됐어요 ↓")

paths = ss.last_paths; meta = ss.last_meta
if paths:
    st.markdown(f"### 미리보기 · {meta.get('topic', '')}")
    n = len(paths); cols = st.columns(min(n, 4))
    for i, p in enumerate(paths):
        with cols[i % len(cols)]:
            if Path(p).exists():
                st.image(p, caption=f"{i+1}/{n}" + (" · 참여유도" if i == n-1 else ""), use_container_width=True)
    caption = st.text_area("인스타 본문 (올리기 전 수정 가능)", height=120, key="preview_caption")
    st.subheader("3. 미리보기 확인 후 올리기")
    usage = usage_summary_for_admin(_buyer())
    st.caption(f"오늘 남은 발행 **{usage['remaining']}**회 · 테스트는 한도 없음")
    if _own_ig(): st.success(f"내 인스타 · {_ig_label()}")
    else: st.warning("즉시/예약은 왼쪽 설정에서 **본인** 인스타 연결이 필요해요. 테스트는 가능.")
    mode = st.radio("올리기 방식", ["테스트발행", "예약발행", "즉시발행"], horizontal=True, key="pm",
        help="테스트=연습 · 예약=나중에 · 즉시=지금")
    sched_dt = None
    if mode == "예약발행":
        from zoneinfo import ZoneInfo
        seoul = ZoneInfo("Asia/Seoul"); now_s = datetime.now(seoul)
        d = st.date_input("예약 날짜 (서울)", value=now_s.date(), key="sd")
        t = st.time_input("예약 시간 (서울)", value=(now_s + timedelta(hours=1)).replace(second=0, microsecond=0).time(), key="stt")
        sched_dt = datetime.combine(d, t).replace(tzinfo=seoul)
    tok = (ss.ig_token or "").strip(); uid = (ss.ig_user_id or "").strip()
    if st.button("실행", type="primary", use_container_width=True, key="run"):
        if mode == "테스트발행":
            r = publish_carousel([Path(p) for p in paths], caption, dry_run=True, access_token=tok or None, ig_user_id=uid or None)
            st.success(r.message + " · 한도 미차감") if r.ok else st.error(r.message)
        elif mode == "즉시발행":
            ok_q, msg_q = can_publish(_buyer())
            if not ok_q: st.error(msg_q)
            elif not _own_ig(): st.error("본인 인스타 연결 키1·키2가 필요해요.")
            else:
                r = publish_carousel([Path(p) for p in paths], caption, dry_run=False, access_token=tok or None, ig_user_id=uid or None)
                if r.ok and not r.dry_run:
                    record_publish(_buyer()); st.success(r.message + f" · 남은 {remaining_today(_buyer())}회")
                else: st.error(r.message or "실패")
        elif mode == "예약발행":
            ok_q, msg_q = can_publish(_buyer())
            if not ok_q: st.error(msg_q)
            elif not _own_ig(): st.error("본인 인스타 연결이 필요해요.")
            elif sched_dt is None: st.error("예약 시간을 확인해 주세요.")
            else:
                ok, msg, _ = add_schedule_job(username=_buyer(), run_at_iso=sched_dt.isoformat(),
                    image_paths=list(paths), caption=caption or "", topic=str(meta.get("topic") or ""))
                st.success(f"{msg} · {sched_dt.strftime('%Y-%m-%d %H:%M')}") if ok else st.error(msg)
else:
    st.caption("주제를 고르고 **카드 만들기**를 누르면 미리보기가 나타나요.")
st.divider()
st.caption("미리보기만 해도 돼요. 인스타 올리기는 선택 사항입니다.")

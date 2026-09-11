"""관리자 전용 (사이드바 숨김 · 로컬 multipage 래퍼). Cloud에서는 ?gate= 메인 URL 사용."""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from src.admin_console import render_admin_console

load_dotenv()

st.set_page_config(page_title="페이지", page_icon="📄", layout="centered")
render_admin_console()

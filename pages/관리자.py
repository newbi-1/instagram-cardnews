"""관리자 페이지 (사이드바에 표시) — 아이디/비밀번호 로그인."""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from src.admin_console import render_admin_console

load_dotenv()

st.set_page_config(page_title="관리자", page_icon="🔐", layout="centered")
render_admin_console()

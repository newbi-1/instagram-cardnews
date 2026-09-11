"""Admin page (sidebar) — username/password login.

English filename so Streamlit Cloud reliably shows the multipage entry.
Korean label via page_title / console UI.

Unauthenticated visitors see only the login form from render_admin_console
(no buyer list or live account data).
"""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from src.admin_console import render_admin_console

load_dotenv()

st.set_page_config(page_title="관리자", page_icon="🔐", layout="centered")
# Do not render buyer lists or account hints here — auth gate is inside console.
render_admin_console()
